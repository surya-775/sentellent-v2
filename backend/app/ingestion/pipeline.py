import json
import logging
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import text as sqltext
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Stock, NewsArticle, NewsChunk, Fundamental, StockSentiment
)
from app.ingestion.chunking import chunk_text, content_hash
from app.ingestion.embeddings import embed_texts
from app.ingestion.news_sources import fetch_all_feeds, RawArticle
from app.ingestion.fundamentals_source import fetch_fundamentals
from app.ingestion.tagging import tag_chunk_for_stock

logger = logging.getLogger(__name__)


@contextmanager
def stock_ingestion_lock(db: Session, stock_id: str):
    """
    Postgres advisory lock scoped to this stock_id, held for the duration of ingestion.
    Guarantees that a scheduled refresh and a manual follow-triggered ingest for the
    SAME stock never run concurrently and race on writes. Other stocks are unaffected.
    Blocks (rather than fails) if already held, so the second caller just waits its turn
    then finds there's nothing new to do (idempotency handles that part).
    """
    # hashtext() -> deterministic 32-bit int key derived from the UUID string
    db.execute(sqltext("SELECT pg_advisory_lock(hashtext(:key))"), {"key": f"ingest:{stock_id}"})
    try:
        yield
    finally:
        db.execute(sqltext("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": f"ingest:{stock_id}"})


def ingest_fundamentals(db: Session, stock: Stock) -> Fundamental:
    snap = fetch_fundamentals(stock.nse_symbol)
    row = Fundamental(
        stock_id=stock.id,
        market_cap_inr=snap.market_cap_inr,
        pe_ratio=snap.pe_ratio,
        pb_ratio=snap.pb_ratio,
        debt_to_equity=snap.debt_to_equity,
        roe_pct=snap.roe_pct,
        dividend_yield_pct=snap.dividend_yield_pct,
        current_price_inr=snap.current_price_inr,
        revenue_growth_pct=snap.revenue_growth_pct,
        profit_growth_pct=snap.profit_growth_pct,
        raw_json=snap.raw_json,
        source_url=snap.source_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_or_create_article(db: Session, raw: RawArticle) -> Optional[NewsArticle]:
    """
    Insert-or-get by content_hash (and url as a secondary uniqueness guard).
    Uses ON CONFLICT DO NOTHING semantics via catching IntegrityError so that two
    concurrent ingestion jobs inserting the same article never create duplicates
    or crash the whole batch.
    """
    h = content_hash(raw.raw_text)
    existing = db.query(NewsArticle).filter(
        (NewsArticle.content_hash == h) | (NewsArticle.url == raw.url)
    ).first()
    if existing:
        return existing

    article = NewsArticle(
        url=raw.url,
        content_hash=h,
        source=raw.source,
        title=raw.title,
        published_at=raw.published_at,
        raw_text=raw.raw_text,
    )
    db.add(article)
    try:
        db.commit()
        db.refresh(article)
        return article
    except IntegrityError:
        # Lost the race to a concurrent inserter (different process/thread) — fetch what they wrote.
        db.rollback()
        return db.query(NewsArticle).filter(
            (NewsArticle.content_hash == h) | (NewsArticle.url == raw.url)
        ).first()


def _update_rolling_sentiment(db: Session, stock_id: str, sentiment: str, event_tags: list):
    """
    Incremental update — touches only this stock's sentiment row, never recomputes
    from the full news history. O(1) per ingested chunk instead of O(n) per ticker.
    """
    row = db.query(StockSentiment).filter(StockSentiment.stock_id == stock_id).first()
    if not row:
        row = StockSentiment(stock_id=stock_id, positive_count=0, negative_count=0, neutral_count=0, rolling_score=0)
        db.add(row)

    if sentiment == "positive":
        row.positive_count = (row.positive_count or 0) + 1
    elif sentiment == "negative":
        row.negative_count = (row.negative_count or 0) + 1
    else:
        row.neutral_count = (row.neutral_count or 0) + 1

    total = (row.positive_count or 0) + (row.negative_count or 0) + (row.neutral_count or 0)
    row.rolling_score = ((row.positive_count or 0) - (row.negative_count or 0)) / total if total else 0

    if sentiment == "negative" and event_tags and "debt" in [t.lower() for t in event_tags]:
        row.debt_flag = True

    db.commit()


def ingest_news_for_stock(db: Session, stock: Stock) -> int:
    """
    Fetch, dedup, chunk, embed, tag, and index news for a single stock.
    Idempotent: re-running with the same source data creates zero new rows,
    because article dedup is by content hash and chunks are uniquely keyed by
    (article_id, stock_id, chunk_index).
    Returns the number of NEW chunks indexed.
    """
    raw_articles = fetch_all_feeds(ticker_hint=stock.nse_symbol, name_hint=stock.name)
    new_chunk_count = 0

    for raw in raw_articles:
        article = _get_or_create_article(db, raw)
        if article is None:
            continue

        # Skip re-chunking if this article was already processed for this stock
        already_indexed = db.query(NewsChunk).filter(
            NewsChunk.article_id == article.id, NewsChunk.stock_id == stock.id
        ).first()
        if already_indexed:
            continue

        pieces = chunk_text(article.raw_text)
        if not pieces:
            continue

        try:
            vectors = embed_texts(pieces)
        except RuntimeError:
            # No embedding key configured (e.g. local dev) — skip embedding but still tag
            vectors = [None] * len(pieces)

        for idx, (piece, vec) in enumerate(zip(pieces, vectors)):
            tag = tag_chunk_for_stock(piece, stock.nse_symbol or stock.name)
            chunk = NewsChunk(
                article_id=article.id,
                stock_id=stock.id,
                chunk_index=idx,
                text=piece,
                embedding=vec,
                sentiment=tag.sentiment,
                impact=tag.impact,
                event_tags=tag.event_tags,
            )
            db.add(chunk)
            try:
                db.commit()
            except IntegrityError:
                # (article_id, stock_id, chunk_index) unique constraint caught a concurrent duplicate insert
                db.rollback()
                continue

            new_chunk_count += 1
            _update_rolling_sentiment(db, stock.id, tag.sentiment, tag.event_tags or [])

    return new_chunk_count


def ingest_stock(db: Session, stock: Stock, refresh_fundamentals: bool = True) -> dict:
    """Top-level entry point: locks on stock_id, then does fundamentals + news idempotently."""
    with stock_ingestion_lock(db, stock.id):
        fundamentals_row = None
        if refresh_fundamentals:
            try:
                fundamentals_row = ingest_fundamentals(db, stock)
            except Exception as e:
                logger.warning(f"Fundamentals fetch failed for {stock.nse_symbol}: {e}")

        new_chunks = ingest_news_for_stock(db, stock)

    return {
        "stock": stock.nse_symbol,
        "new_chunks_indexed": new_chunks,
        "fundamentals_updated": fundamentals_row is not None,
    }
