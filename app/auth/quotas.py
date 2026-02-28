from __future__ import annotations

import hashlib
from contextvars import ContextVar, Token
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserQuotaUsage


MAX_QUOTA_USER_ID_LENGTH = 128
_quota_user_id_ctx: ContextVar[str] = ContextVar("quota_user_id", default="system")


def _normalize_user_id(raw: str) -> str:
    normalized = raw.strip()
    if not normalized:
        return "anonymous"
    return normalized[:MAX_QUOTA_USER_ID_LENGTH]


def resolve_quota_user_id(request: Request | None) -> str:
    if request is not None:
        request_state = getattr(request, "state", None)
        state_user = getattr(request_state, "quota_user_id", "") if request_state is not None else ""
        if isinstance(state_user, str) and state_user.strip():
            return _normalize_user_id(state_user)

        request_headers = getattr(request, "headers", None)
        header_get = request_headers.get if hasattr(request_headers, "get") else (lambda *_args, **_kwargs: "")

        user_id_header = str(header_get("X-User-Id", "")).strip()
        if user_id_header:
            return _normalize_user_id(user_id_header)

        api_key = str(header_get("X-Api-Key", "")).strip()
        if api_key:
            digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:24]
            return _normalize_user_id(f"api:{digest}")

        role = getattr(request_state, "role", "anonymous") if request_state is not None else "anonymous"
        return _normalize_user_id(f"role:{role}")

    return "system"


def set_current_quota_user_id(quota_user_id: str) -> Token[str]:
    return _quota_user_id_ctx.set(_normalize_user_id(quota_user_id))


def reset_current_quota_user_id(token: Token[str]) -> None:
    _quota_user_id_ctx.reset(token)


def current_quota_user_id() -> str:
    return _normalize_user_id(_quota_user_id_ctx.get())


@dataclass(frozen=True)
class QuotaUsageDelta:
    challenges_created: int = 0
    runs_started: int = 0
    artifact_storage_bytes: int = 0


async def get_or_create_quota_usage(session: AsyncSession, quota_user_id: str) -> UserQuotaUsage:
    normalized_user_id = _normalize_user_id(quota_user_id)
    stmt: Select[tuple[UserQuotaUsage]] = select(UserQuotaUsage).where(UserQuotaUsage.quota_user_id == normalized_user_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row

    row = UserQuotaUsage(
        quota_user_id=normalized_user_id,
        challenges_created=0,
        runs_started=0,
        artifact_storage_bytes=0,
    )
    session.add(row)
    await session.flush()
    return row


async def increment_quota_usage(
    session: AsyncSession,
    quota_user_id: str,
    delta: QuotaUsageDelta,
) -> UserQuotaUsage:
    row = await get_or_create_quota_usage(session, quota_user_id)
    row.challenges_created = max(0, row.challenges_created + max(0, delta.challenges_created))
    row.runs_started = max(0, row.runs_started + max(0, delta.runs_started))
    row.artifact_storage_bytes = max(0, row.artifact_storage_bytes + max(0, delta.artifact_storage_bytes))
    await session.flush()
    return row
