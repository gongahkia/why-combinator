from __future__ import annotations

import re

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.quotas import (
    QuotaUsageDelta,
    QuotaExceededError,
    enforce_quota_usage,
    quota_limits_from_settings,
    resolve_quota_user_id,
)


_RUN_START_PATH_PATTERN = re.compile(r"^/challenges/[0-9a-fA-F-]{36}/runs/start$")
_HEALTHCHECK_PATHS = {"/", "/health", "/readiness", "/docs", "/openapi.json", "/redoc"}


def _preflight_quota_delta(request: Request) -> QuotaUsageDelta | None:
    if request.method != "POST":
        return None
    path = request.url.path
    if path == "/challenges":
        return QuotaUsageDelta(challenges_created=1)
    if _RUN_START_PATH_PATTERN.match(path):
        return QuotaUsageDelta(runs_started=1)
    return None


class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        try:
            if request.url.path not in _HEALTHCHECK_PATHS:
                delta = _preflight_quota_delta(request)
                if delta is not None:
                    session_factory = getattr(request.app.state, "db_session_factory", None)
                    limits = quota_limits_from_settings(getattr(request.app.state, "settings", None))
                    if session_factory is not None:
                        async with session_factory() as session:
                            await enforce_quota_usage(
                                session,
                                quota_user_id=resolve_quota_user_id(request),
                                delta=delta,
                                limits=limits,
                            )
            return await call_next(request)
        except QuotaExceededError as exc:
            return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=exc.to_detail())
