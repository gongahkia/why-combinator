from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as redis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.api.challenges import router as challenges_router
from app.api.judges import router as judges_router
from app.api.runs import router as runs_router
from app.api.scoring import router as scoring_router
from app.config import Settings, load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = load_settings()

    db_engine: AsyncEngine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.pg_pool_size,
        max_overflow=settings.pg_max_overflow,
    )
    db_session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    app.state.settings = settings
    app.state.db_engine = db_engine
    app.state.db_session_factory = db_session_factory
    app.state.redis = redis_client

    try:
        yield
    finally:
        await redis_client.aclose()
        await db_engine.dispose()


app = FastAPI(title="Hackathon Service", lifespan=lifespan)
app.include_router(challenges_router)
app.include_router(judges_router)
app.include_router(runs_router)
app.include_router(scoring_router)


@app.get("/", tags=["infra"])
async def root() -> dict[str, str]:
    return {"status": "ok"}
