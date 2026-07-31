import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.news_sources import fetch_all_feeds, RawArticle


_FAKE_ARTICLES = [
    RawArticle(url="https://example.com/1", title="Reliance Industries Q4 profit jumps 15%",
               published_at=None, raw_text="Reliance Industries Q4 profit jumps 15% on retail growth", source="test"),
    RawArticle(url="https://example.com/2", title="TCS signs new outsourcing deal",
               published_at=None, raw_text="TCS signs new outsourcing deal with European bank", source="test"),
    RawArticle(url="https://example.com/3", title="Sensex closes flat amid mixed global cues",
               published_at=None, raw_text="Sensex closes flat amid mixed global cues, IT stocks lag", source="test"),
    RawArticle(url="https://example.com/4", title="RELIANCE announces bonus share issue",
               published_at=None, raw_text="RELIANCE announces bonus share issue for shareholders", source="test"),
]


def _fake_fetch_feed(source, url):
    return _FAKE_ARTICLES


def test_matches_company_name_not_just_bare_ticker():
    """
    The original bug: filtering only on the raw ticker ("RELIANCE") missed articles that
    use the company's display name ("Reliance Industries"), which is what general market
    RSS feeds almost always use. This is the exact case that made news ingestion silently
    return nothing in practice.
    """
    with patch("app.ingestion.news_sources.fetch_feed", side_effect=_fake_fetch_feed):
        results = fetch_all_feeds(ticker_hint="RELIANCE", name_hint="Reliance Industries Ltd")

    urls = {a.url for a in results}
    assert "https://example.com/1" in urls  # matched via company name
    assert "https://example.com/4" in urls  # still matched via bare ticker
    assert "https://example.com/2" not in urls  # unrelated (TCS) must not leak in
    assert "https://example.com/3" not in urls  # unrelated (general market) must not leak in


def test_stopwords_do_not_cause_false_positive_matches():
    """
    Generic tokens like "industries" / "limited" must NOT be used as standalone match
    terms, or every stock whose name contains them would false-positive-match every
    other unrelated "industries" headline.
    """
    with patch("app.ingestion.news_sources.fetch_feed", side_effect=_fake_fetch_feed):
        results = fetch_all_feeds(ticker_hint="SOMEOTHERCO", name_hint="Some Other Industries Ltd")

    # "Industries" alone appears in the Reliance headline too -- if it were used as a
    # match token on its own, this would incorrectly pull in the Reliance article.
    urls = {a.url for a in results}
    assert "https://example.com/1" not in urls


def test_no_hints_returns_everything_unfiltered():
    with patch("app.ingestion.news_sources.fetch_feed", side_effect=_fake_fetch_feed):
        results = fetch_all_feeds()
    assert len(results) == len(_FAKE_ARTICLES)
