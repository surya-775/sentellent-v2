import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

SCREENER_BASE = "https://www.screener.in/company"
_LAST_REQUEST_TS = 0.0
_MIN_INTERVAL_SECONDS = 2.0  # respect rate limits


@dataclass
class FundamentalsSnapshot:
    market_cap_inr: Optional[float]
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    debt_to_equity: Optional[float]
    roe_pct: Optional[float]
    dividend_yield_pct: Optional[float]
    current_price_inr: Optional[float]
    revenue_growth_pct: Optional[float]
    profit_growth_pct: Optional[float]
    source_url: str
    raw_json: dict


def _throttle():
    global _LAST_REQUEST_TS
    elapsed = time.time() - _LAST_REQUEST_TS
    if elapsed < _MIN_INTERVAL_SECONDS:
        time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
    _LAST_REQUEST_TS = time.time()


def _parse_number(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", text)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_growth_tables(soup: BeautifulSoup) -> dict:
    """
    screener.in shows "Compounded Sales Growth" / "Compounded Profit Growth" as separate
    mini-tables (class="ranges-table"), each preceded by a heading naming which one it is,
    with rows like "TTM:" / "10 Years:" -> "12%". This was previously never scraped at all,
    so `revenue_growth_pct` / `profit_growth_pct` stayed NULL forever and the "aggressive"
    persona's growth-scoring boost in scoring.py could never fire.

    Screener's markup shifts between redesigns, so this is deliberately defensive: it walks
    every ranges-table, looks at the nearest preceding heading text to classify it as sales vs
    profit, and prefers the most recent period ("TTM", else the first row) rather than assuming
    a fixed row order. Any failure here just leaves the field None — never raises, since a
    missing "nice-to-have" growth figure should never take down the whole fundamentals fetch.
    """
    growth = {"sales": None, "profit": None}
    for table in soup.select("table.ranges-table"):
        heading = table.find_previous(["p", "h3", "h4", "div"])
        heading_text = heading.get_text(strip=True).lower() if heading else ""
        if "sales" not in heading_text and "profit" not in heading_text:
            continue

        rows = {}
        for tr in table.select("tr"):
            cells = tr.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).rstrip(":").lower()
                rows[label] = _parse_number(cells[1].get_text(strip=True))

        value = rows.get("ttm") or (next(iter(rows.values()), None) if rows else None)
        if value is None:
            continue
        if "sales" in heading_text:
            growth["sales"] = value
        elif "profit" in heading_text:
            growth["profit"] = value

    return growth


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_fundamentals(nse_symbol: str) -> FundamentalsSnapshot:
    """Scrape screener.in's ratio panel for a given NSE symbol. Respects rate limiting + retries transient errors."""
    _throttle()
    url = f"{SCREENER_BASE}/{nse_symbol}/consolidated/"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SentellentBot/1.0; +educational-project)"}

    with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    ratios = {}
    for li in soup.select("#top-ratios li"):
        name_el = li.select_one(".name")
        value_el = li.select_one(".value")
        if name_el and value_el:
            ratios[name_el.get_text(strip=True)] = value_el.get_text(strip=True)

    try:
        growth = _parse_growth_tables(soup)
    except Exception:
        growth = {"sales": None, "profit": None}

    return FundamentalsSnapshot(
        market_cap_inr=_parse_number(ratios.get("Market Cap")),
        pe_ratio=_parse_number(ratios.get("Stock P/E")),
        pb_ratio=_parse_number(ratios.get("P/B")) if "P/B" in ratios else None,
        debt_to_equity=_parse_number(ratios.get("Debt to equity")) if "Debt to equity" in ratios else None,
        roe_pct=_parse_number(ratios.get("ROE")),
        dividend_yield_pct=_parse_number(ratios.get("Dividend Yield")),
        current_price_inr=_parse_number(ratios.get("Current Price")),
        revenue_growth_pct=growth["sales"],
        profit_growth_pct=growth["profit"],
        source_url=url,
        raw_json={**ratios, "_growth": growth},
    )
