import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.db.models import User, ChatMessage
from app.agent.graph import run_agent
from app.api.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(ChatMessage(user_id=user.id, role="user", content=req.message))
    db.commit()

    try:
        result = run_agent(db, user.id, req.message)
    except Exception as e:
        # Last-resort safety net: individual nodes already catch provider errors, but if
        # something else in the graph blows up, still return clean JSON (500 with a message)
        # instead of an unhandled exception, which some proxies turn into a bare connection
        # reset that the browser reports as "Failed to fetch" with zero diagnostic info.
        logger.exception("Agent graph failed")
        raise HTTPException(status_code=502, detail=f"Agent error: {e}")

    db.add(ChatMessage(user_id=user.id, role="assistant", content=result["answer"], citations=result["citations"]))
    db.commit()

    return ChatResponse(answer=result["answer"], citations=result["citations"])


@router.get("/history")
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(200)
        .all()
    )
    return [{"role": m.role, "content": m.content, "citations": m.citations} for m in msgs]
