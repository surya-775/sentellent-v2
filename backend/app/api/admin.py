import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status

from app.core.config import settings
from app.ingestion.scheduler import refresh_all_followed_stocks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.post("/refresh-news")
def trigger_refresh(background_tasks: BackgroundTasks, x_internal_token: str = Header(default="")):
    """
    Runs the same refresh_all_followed_stocks() job the in-process scheduler would run,
    but triggered externally instead. This is the free-tier-friendly replacement for a
    "real" cron service: on Render's free plan (and similar), the web service sleeps after
    15 minutes of inactivity, so an in-process APScheduler job can't be trusted to fire on
    schedule. A GitHub Actions scheduled workflow (free, no card required) calls this
    endpoint on a timer instead — as a side effect, the HTTP request itself also wakes a
    sleeping instance back up.

    Protected by a shared-secret header (not user JWT auth) since this isn't a per-user
    action — comparable to a webhook signature, not a login.
    """
    if not settings.INTERNAL_REFRESH_TOKEN:
        # Failing closed: if no token is configured, refuse rather than silently allow
        # anyone to trigger (and rate-limit-abuse) this job.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Refresh trigger not configured")
    if x_internal_token != settings.INTERNAL_REFRESH_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Run in the background so the HTTP call (and the GitHub Actions job waiting on it)
    # returns quickly rather than blocking on however long a full multi-stock refresh takes.
    background_tasks.add_task(_run_refresh)
    return {"status": "queued"}


def _run_refresh():
    try:
        refresh_all_followed_stocks()
    except Exception:
        logger.exception("Scheduled news refresh failed")
