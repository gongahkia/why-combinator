from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    pg_pool_size: int
    pg_max_overflow: int



def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/hackathon"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        pg_pool_size=int(os.getenv("PG_POOL_SIZE", "10")),
        pg_max_overflow=int(os.getenv("PG_MAX_OVERFLOW", "20")),
    )
