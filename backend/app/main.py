from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.api import auth, stocks, chat, health, admin
from app.ingestion.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort only: on a free-tier instance that sleeps after inactivity, this in-process
    # job won't fire while the process is asleep. The reliable trigger is the external
    # GitHub Actions cron hitting POST /api/internal/refresh-news (see app/api/admin.py) —
    # keeping this too means refreshes still happen on their own if the instance is ever
    # kept warm (e.g. a paid always-on plan later).
    start_scheduler()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(chat.router)
app.include_router(admin.router)
