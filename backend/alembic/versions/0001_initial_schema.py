"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768  # Gemini text-embedding-004


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("google_sub", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("picture_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("google_sub"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_google_sub", "users", ["google_sub"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "stocks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("nse_symbol", sa.String(), nullable=True),
        sa.Column("bse_code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("nse_symbol"),
        sa.UniqueConstraint("bse_code"),
    )
    op.create_index("ix_stocks_symbol_upper", "stocks", ["nse_symbol"])

    op.create_table(
        "follows",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "stock_id", name="uq_user_stock_follow"),
    )

    op.create_table(
        "fundamentals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("stock_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_cap_inr", sa.Numeric(), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(), nullable=True),
        sa.Column("pb_ratio", sa.Numeric(), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(), nullable=True),
        sa.Column("roe_pct", sa.Numeric(), nullable=True),
        sa.Column("dividend_yield_pct", sa.Numeric(), nullable=True),
        sa.Column("revenue_growth_pct", sa.Numeric(), nullable=True),
        sa.Column("profit_growth_pct", sa.Numeric(), nullable=True),
        sa.Column("current_price_inr", sa.Numeric(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fundamentals_stock_fetched", "fundamentals", ["stock_id", "fetched_at"])

    op.create_table(
        "news_articles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("url"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_index("ix_news_articles_url", "news_articles", ["url"])
    op.create_index("ix_news_articles_content_hash", "news_articles", ["content_hash"])

    op.create_table(
        "news_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("sentiment", sa.String(), nullable=True),
        sa.Column("impact", sa.String(), nullable=True),
        sa.Column("event_tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("article_id", "stock_id", "chunk_index", name="uq_article_stock_chunk"),
    )
    op.create_index("ix_news_chunks_stock", "news_chunks", ["stock_id"])
    # IVFFlat index for approximate nearest-neighbor search over embeddings
    op.execute(
        "CREATE INDEX ix_news_chunks_embedding ON news_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "stock_sentiment",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("stock_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("positive_count", sa.Integer(), nullable=True),
        sa.Column("negative_count", sa.Integer(), nullable=True),
        sa.Column("neutral_count", sa.Integer(), nullable=True),
        sa.Column("rolling_score", sa.Numeric(), nullable=True),
        sa.Column("debt_flag", sa.Boolean(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("stock_id"),
    )

    op.create_table(
        "investor_personas",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("risk_profile", sa.String(), nullable=True),
        sa.Column("style_tags", sa.JSON(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "persona_facts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    op.create_table(
        "ingestion_locks",
        sa.Column("stock_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_table("ingestion_locks")
    op.drop_table("chat_messages")
    op.drop_table("persona_facts")
    op.drop_table("investor_personas")
    op.drop_table("stock_sentiment")
    op.drop_table("news_chunks")
    op.drop_table("news_articles")
    op.drop_table("fundamentals")
    op.drop_table("follows")
    op.drop_table("stocks")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
