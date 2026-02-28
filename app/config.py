from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    pg_pool_size: int
    pg_max_overflow: int
    default_run_budget_units: int
    artifact_storage_path: str
    novelty_strategy_mode: str
    quota_limit_challenges_created: int
    quota_limit_runs_started: int
    quota_limit_artifact_storage_bytes: int
    why_combinator_repo_path: str | None
    why_combinator_data_dir: str



def load_settings() -> Settings:
    artifact_storage_path = os.getenv("ARTIFACT_STORAGE_PATH", "/tmp/hackathon-artifacts")
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/hackathon",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        pg_pool_size=int(os.getenv("PG_POOL_SIZE", "10")),
        pg_max_overflow=int(os.getenv("PG_MAX_OVERFLOW", "20")),
        default_run_budget_units=int(os.getenv("DEFAULT_RUN_BUDGET_UNITS", "1000")),
        artifact_storage_path=artifact_storage_path,
        novelty_strategy_mode=os.getenv("NOVELTY_STRATEGY_MODE", "embedding_only"),
        quota_limit_challenges_created=int(os.getenv("QUOTA_LIMIT_CHALLENGES_CREATED", "0")),
        quota_limit_runs_started=int(os.getenv("QUOTA_LIMIT_RUNS_STARTED", "0")),
        quota_limit_artifact_storage_bytes=int(os.getenv("QUOTA_LIMIT_ARTIFACT_STORAGE_BYTES", "0")),
        why_combinator_repo_path=os.getenv("WHY_COMBINATOR_REPO_PATH") or None,
        why_combinator_data_dir=os.getenv(
            "WHY_COMBINATOR_DATA_DIR",
            os.path.join(artifact_storage_path, "why-combinator"),
        ),
    )
