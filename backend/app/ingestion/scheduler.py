import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Stock
from app.ingestion.pipeline import ingest_stock

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler = None


def refresh_all_followed_stocks():
    """
    Cron job: re-ingest every stock that has at least one follower.
    Safe to run concurrently with a manual follow-triggered ingest for the same
    stock — both paths go through ingest_stock's advisory lock + idempotent writes.
    """
    db = SessionLocal()
    try:
        stocks = db.query(Stock).join(Stock.follows).distinct().all()
        for stock in stocks:
            try:
                result = ingest_stock(db, stock)
                logger.info(f"Refreshed {stock.nse_symbol}: {result}")
            except Exception as e:
                logger.warning(f"Refresh failed for {stock.nse_symbol}: {e}")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        refresh_all_followed_stocks,
        "interval",
        minutes=settings.NEWS_REFRESH_INTERVAL_MINUTES,
        id="refresh_followed_stocks",
        max_instances=1,  # prevents overlapping runs of the job itself
    )
    _scheduler.start()
    return _scheduler
