from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class ArtifactPresignError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactDownloadClaims:
    artifact_id: uuid.UUID
    submission_id: uuid.UUID
    expires_at: datetime


def load_artifact_download_signing_key() -> str:
    return os.getenv("ARTIFACT_DOWNLOAD_SIGNING_KEY", "dev-artifact-download-signing-key")


def load_artifact_download_default_ttl_seconds() -> int:
    return int(os.getenv("ARTIFACT_DOWNLOAD_URL_TTL_SECONDS", "300"))


def load_artifact_download_max_ttl_seconds() -> int:
    return int(os.getenv("ARTIFACT_DOWNLOAD_URL_MAX_TTL_SECONDS", "900"))


def _normalize_ttl_seconds(ttl_seconds: int | None) -> int:
    requested = load_artifact_download_default_ttl_seconds() if ttl_seconds is None else int(ttl_seconds)
    if requested <= 0:
        raise ArtifactPresignError("download URL TTL must be positive")
    return min(requested, max(1, load_artifact_download_max_ttl_seconds()))


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign_payload(encoded_payload: str) -> str:
    key = load_artifact_download_signing_key().encode("utf-8")
    return hmac.new(key, encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_artifact_download_token(
    artifact_id: uuid.UUID,
    submission_id: uuid.UUID,
    *,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=UTC)
    ttl = _normalize_ttl_seconds(ttl_seconds)
    expires_at = issued_at + timedelta(seconds=ttl)
    payload = {
        "aid": str(artifact_id),
        "sid": str(submission_id),
        "exp": int(expires_at.timestamp()),
    }
    encoded_payload = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign_payload(encoded_payload)
    return f"{encoded_payload}.{signature}", expires_at


def validate_artifact_download_token(
    token: str,
    *,
    artifact_id: uuid.UUID,
    submission_id: uuid.UUID,
    now: datetime | None = None,
) -> ArtifactDownloadClaims:
    if "." not in token:
        raise ArtifactPresignError("invalid token format")
    encoded_payload, signature = token.split(".", 1)
    expected_signature = _sign_payload(encoded_payload)
    if not hmac.compare_digest(signature, expected_signature):
        raise ArtifactPresignError("token signature mismatch")

    try:
        payload = json.loads(_urlsafe_b64decode(encoded_payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ArtifactPresignError("token payload is malformed") from exc

    if not isinstance(payload, dict):
        raise ArtifactPresignError("token payload is malformed")

    try:
        claim_artifact_id = uuid.UUID(str(payload["aid"]))
        claim_submission_id = uuid.UUID(str(payload["sid"]))
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactPresignError("token payload is malformed") from exc

    if claim_artifact_id != artifact_id or claim_submission_id != submission_id:
        raise ArtifactPresignError("token scope does not match artifact")

    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    if expires_at <= current_time:
        raise ArtifactPresignError("token has expired")

    return ArtifactDownloadClaims(
        artifact_id=claim_artifact_id,
        submission_id=claim_submission_id,
        expires_at=expires_at,
    )
