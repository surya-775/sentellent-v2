import json
from dataclasses import dataclass
from typing import List, Optional

from google import genai
from google.genai import types

from app.core.config import settings

_HTTP_OPTIONS = types.HttpOptions(timeout=15_000)
_client = (
    genai.Client(api_key=settings.GEMINI_API_KEY, http_options=_HTTP_OPTIONS)
    if settings.GEMINI_API_KEY
    else None
)

_SYSTEM_PROMPT = """You tag Indian stock news snippets. Given a snippet and a target stock,
return ONLY compact JSON: {"sentiment": "positive"|"negative"|"neutral", "impact": "high"|"medium"|"low", "event_tags": ["..."]}.
event_tags should be short lowercase tags like "earnings", "debt", "management-change", "regulatory", "sector-trend".
If the snippet doesn't actually mention the stock or has no material content, return sentiment "neutral", impact "low", event_tags []."""


@dataclass
class ChunkTag:
    sentiment: str
    impact: str
    event_tags: List[str]


def tag_chunk_for_stock(text: str, stock_symbol: str) -> ChunkTag:
    """
    One LLM call per NEW chunk at ingest time (cheap, done once, cached forever in the DB).
    This is intentionally NOT done at query time — query-time uses only the stored tags.
    """
    if not _client:
        return ChunkTag(sentiment="neutral", impact="low", event_tags=[])

    try:
        resp = _client.models.generate_content(
            model=settings.CHAT_MODEL,
            contents=f"Stock: {stock_symbol}\nSnippet: {text[:1500]}",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        data = json.loads(resp.text)
        return ChunkTag(
            sentiment=data.get("sentiment", "neutral"),
            impact=data.get("impact", "low"),
            event_tags=data.get("event_tags", []) or [],
        )
    except Exception:
        return ChunkTag(sentiment="neutral", impact="low", event_tags=[])
