from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.quota_enforcement import QuotaEnforcementMiddleware
from app.auth.quotas import (
    QuotaLimits,
    QuotaUsageDelta,
    QuotaExceededError,
    increment_quota_usage,
)


class _SessionScope:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ANN201
        return False


@pytest.mark.asyncio
async def test_increment_quota_usage_raises_structured_over_quota_error(session: AsyncSession) -> None:
    await increment_quota_usage(
        session,
        quota_user_id="quota-user-a",
        delta=QuotaUsageDelta(runs_started=1),
        limits=QuotaLimits(runs_started=1),
    )

    with pytest.raises(QuotaExceededError) as exc_info:
        await increment_quota_usage(
            session,
            quota_user_id="quota-user-a",
            delta=QuotaUsageDelta(runs_started=1),
            limits=QuotaLimits(runs_started=1),
        )

    detail = exc_info.value.to_detail()
    assert detail["code"] == "over_quota"
    assert detail["message"] == "Quota exceeded for runs_started"
    assert detail["details"] == {
        "quota": "runs_started",
        "limit": 1,
        "used": 1,
        "requested": 1,
        "remaining": 0,
        "quota_user_id": "quota-user-a",
    }


@pytest.mark.asyncio
async def test_quota_enforcement_middleware_blocks_preflight_over_quota_request(session: AsyncSession) -> None:
    await increment_quota_usage(
        session,
        quota_user_id="quota-user-b",
        delta=QuotaUsageDelta(challenges_created=1),
    )
    await session.commit()

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/challenges"),
        headers={"X-Role": "organizer", "X-User-Id": "quota-user-b"},
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    quota_limit_challenges_created=1,
                    quota_limit_runs_started=0,
                    quota_limit_artifact_storage_bytes=0,
                ),
                db_session_factory=lambda: _SessionScope(session),
            )
        ),
    )
    middleware = QuotaEnforcementMiddleware(app=lambda scope, receive, send: None)

    called = False

    async def call_next(_request):  # noqa: ANN001
        nonlocal called
        called = True
        return JSONResponse({"ok": True})

    response = await middleware.dispatch(request, call_next)
    payload = json.loads(response.body.decode("utf-8"))

    assert called is False
    assert response.status_code == 429
    assert payload["code"] == "over_quota"
    assert payload["message"] == "Quota exceeded for challenges_created"
    assert payload["details"]["quota"] == "challenges_created"
    assert payload["details"]["limit"] == 1
    assert payload["details"]["used"] == 1
    assert payload["details"]["requested"] == 1
    assert payload["details"]["remaining"] == 0
    assert payload["details"]["quota_user_id"] == "quota-user-b"


@pytest.mark.asyncio
async def test_quota_enforcement_middleware_formats_downstream_over_quota_error() -> None:
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/runs"),
        headers={},
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(), db_session_factory=None)),
    )
    middleware = QuotaEnforcementMiddleware(app=lambda scope, receive, send: None)

    async def call_next(_request):  # noqa: ANN001
        raise QuotaExceededError(
            quota_user_id="quota-user-c",
            quota_name="artifact_storage_bytes",
            limit=1024,
            used=1024,
            requested=256,
        )

    response = await middleware.dispatch(request, call_next)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 429
    assert payload == {
        "code": "over_quota",
        "message": "Quota exceeded for artifact_storage_bytes",
        "details": {
            "quota": "artifact_storage_bytes",
            "limit": 1024,
            "used": 1024,
            "requested": 256,
            "remaining": 0,
            "quota_user_id": "quota-user-c",
        },
    }
