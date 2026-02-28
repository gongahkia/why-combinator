from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta


def build_scoped_model_secret_env(
    base_env: dict[str, str] | None = None,
    ttl_seconds: int = 300,
) -> dict[str, str]:
    scoped_env = dict(base_env or {})
    api_key = os.getenv("MODEL_API_KEY", "")
    if not api_key:
        return scoped_env
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    scoped_env["MODEL_API_KEY"] = api_key
    scoped_env["MODEL_API_KEY_EXPIRES_AT"] = expires_at.isoformat()
    return scoped_env
