from __future__ import annotations

import hashlib
import json

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IdempotencyKey


def hash_request_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def get_idempotent_response(
    session: AsyncSession,
    scope: str,
    key: str,
    request_hash: str,
) -> dict[str, object] | None:
    stmt: Select[tuple[IdempotencyKey]] = select(IdempotencyKey).where(
        and_(
            IdempotencyKey.scope == scope,
            IdempotencyKey.key == key,
            IdempotencyKey.request_hash == request_hash,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return None if row is None else row.response_payload


async def store_idempotent_response(
    session: AsyncSession,
    scope: str,
    key: str,
    request_hash: str,
    response_payload: dict[str, object],
) -> None:
    session.add(
        IdempotencyKey(
            scope=scope,
            key=key,
            request_hash=request_hash,
            response_payload=response_payload,
        )
    )
    await session.flush()
