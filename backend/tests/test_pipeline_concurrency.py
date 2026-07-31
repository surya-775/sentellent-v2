import sys
import os
from unittest.mock import MagicMock
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.pipeline import _get_or_create_article
from app.ingestion.news_sources import RawArticle


def _make_article_row(raw: RawArticle, article_id="existing-id"):
    row = MagicMock()
    row.id = article_id
    row.url = raw.url
    return row


def test_get_or_create_article_returns_existing_when_already_present():
    """Simple case: article already in DB (by content_hash or url) -> no insert attempted."""
    raw = RawArticle(url="https://example.com/a", title="RELIANCE hits new high",
                      published_at=None, raw_text="RELIANCE hits new high today", source="test")
    existing_row = _make_article_row(raw)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing_row

    result = _get_or_create_article(db, raw)

    assert result is existing_row
    db.add.assert_not_called()  # never even attempts an insert


def test_get_or_create_article_handles_concurrent_insert_race():
    """
    Simulates two ingestion jobs racing on the SAME article: this caller's SELECT sees
    nothing yet (first().return_value = None on the first call), so it tries to INSERT,
    but the other job's commit landed first and the DB-level unique constraint fires as
    an IntegrityError. The pipeline must catch that, roll back, and re-fetch what the
    winner wrote -- never crash, never create a duplicate row.
    """
    raw = RawArticle(url="https://example.com/b", title="TCS wins big deal",
                      published_at=None, raw_text="TCS wins big deal worth Rs. 500 crore", source="test")
    winner_row = _make_article_row(raw, article_id="winner-id")

    db = MagicMock()
    # First SELECT (before insert attempt): nothing found yet.
    # Second SELECT (after IntegrityError, re-fetching the winner's row): found.
    db.query.return_value.filter.return_value.first.side_effect = [None, winner_row]
    db.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate key"))

    result = _get_or_create_article(db, raw)

    assert result is winner_row
    db.rollback.assert_called_once()  # must roll back the failed insert, not leave the session poisoned


def test_get_or_create_article_is_idempotent_for_reingested_identical_content():
    """
    Running ingestion twice on the exact same article content (even from a different URL,
    e.g. two RSS feeds syndicating the same wire story) must not create a second row --
    dedup is by content_hash OR url, so the second call is a pure lookup, no insert.
    """
    raw = RawArticle(url="https://mirror.example.com/b", title="TCS wins big deal",
                      published_at=None, raw_text="TCS wins big deal worth Rs. 500 crore", source="test-mirror")
    already_indexed = _make_article_row(raw, article_id="original-id")

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = already_indexed

    result = _get_or_create_article(db, raw)

    assert result is already_indexed
    db.add.assert_not_called()
    db.commit.assert_not_called()
