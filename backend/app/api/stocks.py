from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.db.models import User, Stock, Follow
from app.ingestion.pipeline import ingest_stock
from app.api.schemas import FollowStockRequest, StockOut

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.post("/follow")
def follow_stock(
    req: FollowStockRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    symbol = req.nse_symbol.upper().strip()
    stock = db.query(Stock).filter(Stock.nse_symbol == symbol).first()
    if not stock:
        stock = Stock(nse_symbol=symbol, name=req.name or symbol)
        db.add(stock)
        db.commit()
        db.refresh(stock)

    existing_follow = db.query(Follow).filter(Follow.user_id == user.id, Follow.stock_id == stock.id).first()
    if not existing_follow:
        follow = Follow(user_id=user.id, stock_id=stock.id)
        db.add(follow)
        db.commit()

    # Ingestion runs in the background so the follow action returns immediately;
    # the pipeline itself is idempotent/lock-safe if triggered again concurrently.
    background_tasks.add_task(_run_ingest, stock.id)

    return {"followed": symbol, "ingestion": "queued"}


def _run_ingest(stock_id: str):
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if stock:
            ingest_stock(db, stock)
    finally:
        db.close()


@router.get("/followed", response_model=list[StockOut])
def list_followed(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    follows = db.query(Follow).filter(Follow.user_id == user.id).all()
    return [f.stock for f in follows]
