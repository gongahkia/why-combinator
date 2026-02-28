from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware


ROLE_HEADER = "X-Role"
CHALLENGE_ACCESS_HEADER = "X-Challenge-Access"
_CHALLENGE_PATH_PATTERN = re.compile(r"^/challenges/([0-9a-fA-F-]{36})(?:/|$)")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.url.path in {"/", "/health", "/readiness", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        role = request.headers.get(ROLE_HEADER, "").strip().lower()
        if role not in {"organizer", "participant"}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing or invalid role")

        request.state.role = role
        allowed_challenge_ids = {
            item.strip()
            for item in request.headers.get(CHALLENGE_ACCESS_HEADER, "").split(",")
            if item.strip()
        }
        request.state.allowed_challenge_ids = allowed_challenge_ids

        challenge_match = _CHALLENGE_PATH_PATTERN.match(request.url.path)
        if challenge_match and role == "participant":
            challenge_id = challenge_match.group(1)
            try:
                uuid.UUID(challenge_id)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid challenge id path") from exc
            if challenge_id not in allowed_challenge_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="participant not authorized for challenge")

        return await call_next(request)
