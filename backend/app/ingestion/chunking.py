import hashlib
import re
from typing import List

from app.core.config import settings


def normalize_text(text: str) -> str:
    """Collapse whitespace and lowercase-normalize punctuation spacing for stable hashing."""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_hash(text: str) -> str:
    """Stable hash used as the dedup key across sources — same article from two RSS feeds hashes the same."""
    normalized = normalize_text(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    """Simple sliding-window chunker on whitespace-normalized text, sized in characters."""
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    text = normalize_text(text)
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks
