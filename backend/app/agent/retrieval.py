from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy import text as sqltext
from sqlalchemy.orm import Session

from app.db.models import Stock, Fundamental
from app.ingestion.embeddings import embed_text


@dataclass
class RetrievedChunk:
    chunk_id: str
    stock_symbol: str
    text: str
    sentiment: str
    impact: str
    source_title: str
    source_url: str
    similarity: float


def retrieve_news_chunks(db: Session, query: str, stock_symbols: Optional[List[str]] = None, k: int = 6) -> List[RetrievedChunk]:
    """
    Cosine-similarity search over pgvector, optionally filtered to a set of tickers.
    Filtering happens in SQL (metadata + vector index together), not by pulling
    everything and re-ranking with an LLM.
    """
    query_vec = embed_text(query)
    vec_literal = "[" + ",".join(str(x) for x in query_vec) + "]"

    filter_clause = ""
    params = {"qvec": vec_literal, "k": k}
    if stock_symbols:
        filter_clause = "AND s.nse_symbol = ANY(:symbols)"
        params["symbols"] = stock_symbols

    sql = f"""
        SELECT nc.id, s.nse_symbol, nc.text, nc.sentiment, nc.impact,
               na.title, na.url,
               1 - (nc.embedding <=> :qvec) AS similarity
        FROM news_chunks nc
        JOIN stocks s ON s.id = nc.stock_id
        JOIN news_articles na ON na.id = nc.article_id
        WHERE nc.embedding IS NOT NULL
        {filter_clause}
        ORDER BY nc.embedding <=> :qvec
        LIMIT :k
    """
    rows = db.execute(sqltext(sql), params).fetchall()
    return [
        RetrievedChunk(
            chunk_id=str(r[0]), stock_symbol=r[1], text=r[2], sentiment=r[3], impact=r[4],
            source_title=r[5], source_url=r[6], similarity=float(r[7]),
        )
        for r in rows
    ]


def get_latest_fundamentals(db: Session, stock_symbol: str) -> Optional[Fundamental]:
    """Simple indexed lookup (stock_id, fetched_at) — no re-computation, just the latest cached snapshot."""
    return (
        db.query(Fundamental)
        .join(Stock, Stock.id == Fundamental.stock_id)
        .filter(Stock.nse_symbol == stock_symbol)
        .order_by(Fundamental.fetched_at.desc())
        .first()
    )
