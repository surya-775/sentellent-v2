from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "Sentellent Stock Analyst"
    ENV: str = "dev"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/stockanalyst"

    # Auth
    JWT_SECRET: str = "change-me-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:3000"

    # Shared secret for the external cron trigger (see app/api/admin.py + .github/workflows/news-refresh.yml).
    # Free-tier web services (Render's free plan, etc.) sleep after inactivity, so an in-process APScheduler
    # job can silently stop firing — an external, authenticated HTTP trigger is the reliable free alternative.
    INTERNAL_REFRESH_TOKEN: str = ""

    # LLM / embeddings
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    CHAT_MODEL: str = "gemini-flash-latest"

    # Ingestion
    NEWS_REFRESH_INTERVAL_MINUTES: int = 60
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120


settings = Settings()
