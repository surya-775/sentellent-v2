import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.chunking import chunk_text, content_hash, normalize_text
from app.agent.scoring import score_stock


def test_normalize_text_collapses_whitespace():
    assert normalize_text("hello   \n\n world  ") == "hello world"


def test_content_hash_is_stable_across_sources():
    a = "RELIANCE reported strong  Q4 results."
    b = "reliance   reported strong q4 results."
    assert content_hash(a) == content_hash(b)


def test_content_hash_differs_for_different_text():
    assert content_hash("TCS wins big deal") != content_hash("Infosys wins big deal")


def test_chunk_text_short_text_single_chunk():
    text = "short article"
    chunks = chunk_text(text, chunk_size=800, overlap=120)
    assert chunks == ["short article"]


def test_chunk_text_long_text_produces_overlapping_chunks():
    text = "word " * 1000  # ~5000 chars
    chunks = chunk_text(text, chunk_size=800, overlap=120)
    assert len(chunks) > 1
    # verify overlap: end of chunk[0] should share content with start of chunk[1]
    assert chunks[0][-50:] in text
    assert len(chunks[0]) <= 800


def test_chunk_text_empty_returns_empty_list():
    assert chunk_text("", chunk_size=800, overlap=120) == []


class FakePersona:
    def __init__(self, risk_profile="conservative", style_tags=None):
        self.risk_profile = risk_profile
        self.style_tags = style_tags or []


class FakeFundamentals:
    def __init__(self, debt_to_equity=None, dividend_yield_pct=None, roe_pct=None, revenue_growth_pct=None):
        self.debt_to_equity = debt_to_equity
        self.dividend_yield_pct = dividend_yield_pct
        self.roe_pct = roe_pct
        self.revenue_growth_pct = revenue_growth_pct


class FakeSentiment:
    def __init__(self, rolling_score=0, debt_flag=False):
        self.rolling_score = rolling_score
        self.debt_flag = debt_flag


def test_score_stock_penalizes_high_debt_for_debt_averse_persona():
    persona = FakePersona(risk_profile="conservative", style_tags=["avoids high debt"])
    fundamentals = FakeFundamentals(debt_to_equity=1.5)
    sentiment = FakeSentiment(rolling_score=0.2, debt_flag=True)
    score = score_stock(fundamentals, sentiment, persona)
    assert score < 0  # heavily penalized


def test_score_stock_rewards_dividend_yield_for_dividend_focused_persona():
    persona = FakePersona(risk_profile="conservative", style_tags=["dividend-focused"])
    fundamentals = FakeFundamentals(debt_to_equity=0.3, dividend_yield_pct=4.0)
    sentiment = FakeSentiment(rolling_score=0.1, debt_flag=False)
    score = score_stock(fundamentals, sentiment, persona)
    assert score > 0


def test_score_stock_rewards_revenue_growth_for_aggressive_persona():
    """
    Regression test for the growth-scoring boost: previously fetch_fundamentals() never
    populated revenue_growth_pct, so this branch in score_stock() could never fire even
    though the logic for it existed. Now that the scraper fills it in, confirm the boost
    actually applies for an aggressive-risk persona and not for a conservative one.
    """
    aggressive = FakePersona(risk_profile="aggressive", style_tags=[])
    conservative = FakePersona(risk_profile="conservative", style_tags=[])
    fundamentals = FakeFundamentals(revenue_growth_pct=18.0)
    sentiment = FakeSentiment(rolling_score=0)

    aggressive_score = score_stock(fundamentals, sentiment, aggressive)
    conservative_score = score_stock(fundamentals, sentiment, conservative)

    assert aggressive_score > conservative_score


def test_score_stock_is_deterministic():
    persona = FakePersona()
    fundamentals = FakeFundamentals(debt_to_equity=0.5, roe_pct=15)
    sentiment = FakeSentiment(rolling_score=0.3)
    s1 = score_stock(fundamentals, sentiment, persona)
    s2 = score_stock(fundamentals, sentiment, persona)
    assert s1 == s2
