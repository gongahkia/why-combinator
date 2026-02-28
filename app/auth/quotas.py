from __future__ import annotations

import hashlib
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class QuotaLimits:
    challenges_created: int | None = None
    runs_started: int | None = None
    artifact_storage_bytes: int | None = None


class QuotaExceededError(RuntimeError):
    def __init__(
        self,
        *,
        quota_user_id: str,
        quota_name: str,
        limit: int,
        used: int,
        requested: int,
    ) -> None:
        self.quota_user_id = _normalize_user_id(quota_user_id)
        self.quota_name = quota_name
        self.limit = max(0, limit)
        self.used = max(0, used)
        self.requested = max(0, requested)
        self.remaining = max(0, self.limit - self.used)
        super().__init__(f"over quota for {self.quota_name}")

    def to_detail(self) -> dict[str, object]:
        return {
            "code": "over_quota",
            "message": f"Quota exceeded for {self.quota_name}",
            "details": {
                "quota": self.quota_name,
                "limit": self.limit,
                "used": self.used,
                "requested": self.requested,
                "remaining": self.remaining,
                "quota_user_id": self.quota_user_id,
            },
        }


def _normalize_quota_limit(value: int | None) -> int | None:
    if value is None:
        return None
    if value <= 0:
        return None
    return value


def quota_limits_from_settings(settings: Any | None) -> QuotaLimits:
    if settings is None:
        return QuotaLimits()
    return QuotaLimits(
        challenges_created=_normalize_quota_limit(getattr(settings, "quota_limit_challenges_created", 0)),
        runs_started=_normalize_quota_limit(getattr(settings, "quota_limit_runs_started", 0)),
        artifact_storage_bytes=_normalize_quota_limit(getattr(settings, "quota_limit_artifact_storage_bytes", 0)),
    )


def quota_limits_from_request(request: Request | None) -> QuotaLimits:
    if request is None:
        return QuotaLimits()
    app_state = getattr(getattr(request, "app", None), "state", None)
    settings = getattr(app_state, "settings", None)
    return quota_limits_from_settings(settings)


def _normalized_delta(delta: QuotaUsageDelta) -> QuotaUsageDelta:
    return QuotaUsageDelta(
        challenges_created=max(0, delta.challenges_created),
        runs_started=max(0, delta.runs_started),
        artifact_storage_bytes=max(0, delta.artifact_storage_bytes),
    )


def _assert_quota_delta_allowed(
    *,
    quota_user_id: str,
    usage: UserQuotaUsage,
    delta: QuotaUsageDelta,
    limits: QuotaLimits,
) -> None:
    checks: tuple[tuple[str, int, int, int | None], ...] = (
        ("challenges_created", usage.challenges_created, delta.challenges_created, limits.challenges_created),
        ("runs_started", usage.runs_started, delta.runs_started, limits.runs_started),
        ("artifact_storage_bytes", usage.artifact_storage_bytes, delta.artifact_storage_bytes, limits.artifact_storage_bytes),
    )
    for quota_name, used, requested, limit in checks:
        if requested <= 0 or limit is None:
            continue
        if used + requested > limit:
            raise QuotaExceededError(
                quota_user_id=quota_user_id,
                quota_name=quota_name,
                limit=limit,
                used=used,
                requested=requested,
            )


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


async def enforce_quota_usage(
    session: AsyncSession,
    quota_user_id: str,
    delta: QuotaUsageDelta,
    *,
    limits: QuotaLimits,
) -> UserQuotaUsage:
    normalized_user_id = _normalize_user_id(quota_user_id)
    normalized_delta = _normalized_delta(delta)
    row = await get_or_create_quota_usage(session, normalized_user_id)
    _assert_quota_delta_allowed(
        quota_user_id=normalized_user_id,
        usage=row,
        delta=normalized_delta,
        limits=limits,
    )
    return row


async def increment_quota_usage(
    session: AsyncSession,
    quota_user_id: str,
    delta: QuotaUsageDelta,
    *,
    limits: QuotaLimits | None = None,
) -> UserQuotaUsage:
    normalized_user_id = _normalize_user_id(quota_user_id)
    normalized_delta = _normalized_delta(delta)
    row = await get_or_create_quota_usage(session, normalized_user_id)
    if limits is not None:
        _assert_quota_delta_allowed(
            quota_user_id=normalized_user_id,
            usage=row,
            delta=normalized_delta,
            limits=limits,
        )
    row.challenges_created = max(0, row.challenges_created + normalized_delta.challenges_created)
    row.runs_started = max(0, row.runs_started + normalized_delta.runs_started)
    row.artifact_storage_bytes = max(0, row.artifact_storage_bytes + normalized_delta.artifact_storage_bytes)
    await session.flush()
    return row
