import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Numeric,
    Enum, UniqueConstraint, Index, Integer, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db.session import Base
from app.core.config import settings


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    google_sub = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    follows = relationship("Follow", back_populates="user", cascade="all, delete-orphan")
    persona = relationship("InvestorPersona", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    nse_symbol = Column(String, unique=True, index=True, nullable=True)   # e.g. RELIANCE
    bse_code = Column(String, unique=True, index=True, nullable=True)     # e.g. 500325
    name = Column(String, nullable=False)
    sector = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    fundamentals = relationship("Fundamental", back_populates="stock", cascade="all, delete-orphan")
    news_chunks = relationship("NewsChunk", back_populates="stock", cascade="all, delete-orphan")
    follows = relationship("Follow", back_populates="stock", cascade="all, delete-orphan")
    sentiment = relationship("StockSentiment", back_populates="stock", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_stocks_symbol_upper", "nse_symbol"),
    )


class Follow(Base):
    """User <-> Stock follow relationship. Triggers ingestion on creation."""
    __tablename__ = "follows"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stock_id = Column(UUID(as_uuid=False), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="follows")
    stock = relationship("Stock", back_populates="follows")

    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", name="uq_user_stock_follow"),
    )


class Fundamental(Base):
    """A point-in-time snapshot of a stock's fundamentals (from screener.in)."""
    __tablename__ = "fundamentals"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    stock_id = Column(UUID(as_uuid=False), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)

    market_cap_inr = Column(Numeric, nullable=True)
    pe_ratio = Column(Numeric, nullable=True)
    pb_ratio = Column(Numeric, nullable=True)
    debt_to_equity = Column(Numeric, nullable=True)
    roe_pct = Column(Numeric, nullable=True)
    dividend_yield_pct = Column(Numeric, nullable=True)
    revenue_growth_pct = Column(Numeric, nullable=True)
    profit_growth_pct = Column(Numeric, nullable=True)
    current_price_inr = Column(Numeric, nullable=True)

    raw_json = Column(JSON, nullable=True)   # full scraped payload for audit/citation
    source_url = Column(String, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)

    stock = relationship("Stock", back_populates="fundamentals")

    __table_args__ = (
        Index("ix_fundamentals_stock_fetched", "stock_id", "fetched_at"),
    )


class NewsArticle(Base):
    """Deduplicated source article (dedup key = content hash + canonical URL)."""
    __tablename__ = "news_articles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    url = Column(String, unique=True, nullable=False, index=True)
    content_hash = Column(String, unique=True, nullable=False, index=True)  # sha256 of normalized text, dedup guard
    source = Column(String, nullable=False)   # e.g. "moneycontrol", "economictimes"
    title = Column(Text, nullable=False)
    published_at = Column(DateTime, nullable=True)
    raw_text = Column(Text, nullable=False)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("NewsChunk", back_populates="article", cascade="all, delete-orphan")


class NewsChunk(Base):
    """Embedded chunk of a NewsArticle, tagged with per-stock sentiment/impact by an LLM pass."""
    __tablename__ = "news_chunks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    article_id = Column(UUID(as_uuid=False), ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)
    stock_id = Column(UUID(as_uuid=False), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)

    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)

    sentiment = Column(String, nullable=True)   # positive | negative | neutral
    impact = Column(String, nullable=True)      # e.g. "high", "medium", "low"
    event_tags = Column(JSON, nullable=True)    # e.g. ["earnings", "debt", "management-change"]

    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("NewsArticle", back_populates="chunks")
    stock = relationship("Stock", back_populates="news_chunks")

    __table_args__ = (
        UniqueConstraint("article_id", "stock_id", "chunk_index", name="uq_article_stock_chunk"),
        Index("ix_news_chunks_stock", "stock_id"),
    )


class StockSentiment(Base):
    """Rolling aggregated sentiment per stock, updated incrementally on ingest (not recomputed from scratch)."""
    __tablename__ = "stock_sentiment"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    stock_id = Column(UUID(as_uuid=False), ForeignKey("stocks.id", ondelete="CASCADE"), unique=True, nullable=False)

    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    rolling_score = Column(Numeric, default=0)   # e.g. weighted -1..1, decayed over time
    debt_flag = Column(Boolean, default=False)   # set true if recent negative+debt event tagged
    last_updated = Column(DateTime, default=datetime.utcnow)

    stock = relationship("Stock", back_populates="sentiment")


class InvestorPersona(Base):
    """One persona per user: extracted preferences + an embedding for persona-stock matching."""
    __tablename__ = "investor_personas"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    risk_profile = Column(String, nullable=True)          # conservative | moderate | aggressive
    style_tags = Column(JSON, nullable=True)               # e.g. ["dividend-focused", "avoids high debt"]
    summary_text = Column(Text, nullable=True)              # human-readable rolled-up persona description
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="persona")


class PersonaFact(Base):
    """Append-only log of individual facts extracted from chat, feeding persona summary regeneration."""
    __tablename__ = "persona_facts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fact_text = Column(Text, nullable=False)
    source = Column(String, default="chat")   # chat | inferred
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)   # user | assistant
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)  # list of {type, id, label}
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class IngestionLock(Base):
    """Advisory lock row to make concurrent ingestion jobs for the same stock idempotent/safe."""
    __tablename__ = "ingestion_locks"

    stock_id = Column(UUID(as_uuid=False), ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String, nullable=True)
