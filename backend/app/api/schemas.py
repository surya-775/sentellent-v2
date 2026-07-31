from typing import List, Optional
from pydantic import BaseModel


class FollowStockRequest(BaseModel):
    nse_symbol: str
    name: Optional[str] = None


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    citations: List[dict]


class StockOut(BaseModel):
    nse_symbol: Optional[str]
    name: str
    sector: Optional[str]

    class Config:
        from_attributes = True
