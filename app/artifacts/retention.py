from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta


class ArtifactRetentionPolicyError(ValueError):
    pass


def load_default_artifact_retention_ttl_seconds() -> int:
    return int(os.getenv("ARTIFACT_RETENTION_DEFAULT_TTL_SECONDS", str(30 * 24 * 60 * 60)))


def _validate_ttl_seconds(ttl_seconds: int) -> int:
    if ttl_seconds <= 0:
        raise ArtifactRetentionPolicyError("artifact retention TTL must be positive")
    if ttl_seconds > 365 * 24 * 60 * 60:
        raise ArtifactRetentionPolicyError("artifact retention TTL exceeds maximum of 365 days")
    return ttl_seconds


def resolve_artifact_retention_ttl_seconds(challenge_override_seconds: int | None) -> int:
    if challenge_override_seconds is not None:
        return _validate_ttl_seconds(int(challenge_override_seconds))
    return _validate_ttl_seconds(load_default_artifact_retention_ttl_seconds())


def compute_artifact_expiry(
    *,
    created_at: datetime | None = None,
    challenge_override_seconds: int | None = None,
) -> datetime:
    base_time = created_at or datetime.now(UTC)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=UTC)
    ttl_seconds = resolve_artifact_retention_ttl_seconds(challenge_override_seconds)
    return base_time + timedelta(seconds=ttl_seconds)


def is_artifact_expired(expires_at: datetime | None, now: datetime | None = None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    return expires_at <= current_time
