import logging
from functools import lru_cache
from typing import List

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fail fast instead of hanging: the SDK has no timeout by default, and a stuck
# outbound call here (bad network path, bad key, Google-side slowness) would
# otherwise block a request thread until the ALB/API Gateway idle timeout kills
# the client connection — which surfaces to the browser as a bare "Failed to
# fetch" with no useful error at all.
_HTTP_OPTIONS = types.HttpOptions(timeout=15_000)  # milliseconds

_client = (
    genai.Client(api_key=settings.GEMINI_API_KEY, http_options=_HTTP_OPTIONS)
    if settings.GEMINI_API_KEY
    else None
)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch-embed a list of texts in a single API call — avoids per-chunk round trips."""
    if not _client:
        raise RuntimeError("GEMINI_API_KEY not configured")
    if not texts:
        return []
    try:
        resp = _client.models.embed_content(model=settings.EMBEDDING_MODEL, contents=texts)
        return [e.values for e in resp.embeddings]
    except Exception as e:
        logger.warning(f"Embedding call failed: {e}")
        raise RuntimeError(f"Embedding provider error: {e}") from e


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]
