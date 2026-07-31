from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import Stock, Fundamental, StockSentiment, InvestorPersona


@dataclass
class ScoredStock:
    symbol: str
    name: str
    score: float
    reason: str
    debt_flag: bool
    sentiment_score: float


def score_stock(fundamentals: Optional[Fundamental], sentiment: Optional[StockSentiment], persona: InvestorPersona) -> float:
    """
    Deterministic, testable scoring function — no LLM call. Weighted sum of normalized
    signals, adjusted by persona risk profile and style tags. Pure function of its inputs,
    so it's cheap to run against every followed stock on every query.
    """
    score = 0.0
    style_tags = [t.lower() for t in (persona.style_tags or [])]
    avoids_high_debt = "avoids high debt" in style_tags or "avoid high-debt companies" in style_tags
    dividend_focused = "dividend-focused" in style_tags

    if sentiment:
        score += float(sentiment.rolling_score or 0) * 2.0
        if sentiment.debt_flag and (avoids_high_debt or persona.risk_profile == "conservative"):
            score -= 3.0  # hard penalty, screens out the name in practice

    if fundamentals:
        if fundamentals.debt_to_equity is not None:
            if avoids_high_debt and float(fundamentals.debt_to_equity) > 1.0:
                score -= 2.0
            elif float(fundamentals.debt_to_equity) < 0.5:
                score += 0.5

        if dividend_focused and fundamentals.dividend_yield_pct:
            score += min(float(fundamentals.dividend_yield_pct) / 2.0, 2.0)

        if fundamentals.roe_pct:
            score += min(float(fundamentals.roe_pct) / 20.0, 1.0)

        if persona.risk_profile == "aggressive" and fundamentals.revenue_growth_pct:
            score += min(float(fundamentals.revenue_growth_pct) / 15.0, 1.5)

    return round(score, 3)


def rank_followed_stocks(db: Session, user_id: str, persona: InvestorPersona) -> List[ScoredStock]:
    """Score every stock the user follows against their persona. O(followed stocks), not O(all Nifty stocks) per query."""
    from app.db.models import Follow

    follows = db.query(Follow).filter(Follow.user_id == user_id).all()
    results = []
    for f in follows:
        stock: Stock = f.stock
        fundamentals = (
            db.query(Fundamental)
            .filter(Fundamental.stock_id == stock.id)
            .order_by(Fundamental.fetched_at.desc())
            .first()
        )
        sentiment = db.query(StockSentiment).filter(StockSentiment.stock_id == stock.id).first()

        s = score_stock(fundamentals, sentiment, persona)

        reason_parts = []
        if sentiment and sentiment.debt_flag:
            reason_parts.append("flagged for rising debt")
        elif sentiment and (sentiment.rolling_score or 0) > 0.3:
            reason_parts.append("recent positive sentiment")
        if fundamentals and fundamentals.dividend_yield_pct:
            reason_parts.append(f"{fundamentals.dividend_yield_pct}% dividend yield")
        reason = "; ".join(reason_parts) or "matched on available fundamentals"

        results.append(ScoredStock(
            symbol=stock.nse_symbol, name=stock.name, score=s, reason=reason,
            debt_flag=bool(sentiment.debt_flag) if sentiment else False,
            sentiment_score=float(sentiment.rolling_score) if sentiment else 0.0,
        ))

    return sorted(results, key=lambda x: x.score, reverse=True)
