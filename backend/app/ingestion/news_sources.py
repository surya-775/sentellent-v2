from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import feedparser
from bs4 import BeautifulSoup

# Indian financial media RSS feeds. Extend as needed.
RSS_FEEDS = {
    "moneycontrol": "https://www.moneycontrol.com/rss/marketreports.xml",
    "economictimes": "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146842.cms",
    "livemint": "https://www.livemint.com/rss/markets",
    "business-standard": "https://www.business-standard.com/rss/markets-106.rss",
}


@dataclass
class RawArticle:
    url: str
    title: str
    published_at: Optional[datetime]
    raw_text: str
    source: str


def _clean_html(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(separator=" ", strip=True)


def fetch_feed(source: str, url: str) -> List[RawArticle]:
    parsed = feedparser.parse(url)
    articles = []
    for entry in parsed.entries:
        summary = _clean_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        title = getattr(entry, "title", "")
        link = getattr(entry, "link", "")
        if not link or not (title or summary):
            continue
        published_at = None
        if getattr(entry, "published_parsed", None):
            published_at = datetime(*entry.published_parsed[:6])
        articles.append(RawArticle(
            url=link,
            title=title,
            published_at=published_at,
            raw_text=f"{title}. {summary}",
            source=source,
        ))
    return articles


def fetch_all_feeds(ticker_hint: Optional[str] = None, name_hint: Optional[str] = None) -> List[RawArticle]:
    """
    Fetch all configured feeds. Filters to articles mentioning the stock, matched against
    BOTH the bare NSE symbol and the company's display name — general market RSS feeds
    almost always use the company name ("Reliance Industries"), rarely the raw ticker
    ("RELIANCE"), so matching on the symbol alone would miss nearly everything.
    """
    all_articles = []
    for source, url in RSS_FEEDS.items():
        try:
            all_articles.extend(fetch_feed(source, url))
        except Exception:
            # A single feed failing shouldn't break ingestion for the rest
            continue

    needles = [h.lower() for h in (ticker_hint, name_hint) if h]
    if name_hint:
        # Also match on individual significant words ("Reliance" out of "Reliance Industries Ltd") —
        # headlines rarely use the full registered name, and generic words like "ltd"/"industries"
        # would cause false positives, so only keep longer, more distinctive tokens.
        STOPWORDS = {"ltd", "limited", "industries", "corporation", "corp", "company", "co", "the", "and", "of"}
        needles += [w.lower() for w in name_hint.split() if len(w) > 3 and w.lower() not in STOPWORDS]
    if needles:
        all_articles = [
            a for a in all_articles
            if any(n in a.raw_text.lower() or n in a.title.lower() for n in needles)
        ]
    return all_articles
