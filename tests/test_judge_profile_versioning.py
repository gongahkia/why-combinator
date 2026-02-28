from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.judges import (
    JudgeProfileRegisterJSONRequest,
    JudgeProfileVersionActivateRequest,
    JudgeProfileInput,
    activate_judge_profile_version,
    list_judge_profile_versions,
    register_judge_profiles_csv,
    register_judge_profiles_json,
)
from app.db.models import Challenge, JudgeProfileVersion


@pytest.mark.asyncio
async def test_judge_profile_mutations_create_incremental_active_versions(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Judge profile versioning",
        prompt="Track active and historical judge profile versions.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.1,
        risk_appetite="balanced",
        complexity_slider=0.4,
    )
    session.add(challenge)
    await session.commit()

    await register_judge_profiles_json(
        challenge.id,
        JudgeProfileRegisterJSONRequest(
            profiles=[
                JudgeProfileInput(
                    domain="ops",
                    scoring_style="balanced",
                    profile_prompt="Evaluate operational quality.",
                    head_judge=True,
                )
            ]
        ),
        session=session,
    )
    await register_judge_profiles_csv(
        challenge.id,
        "domain,scoring_style,profile_prompt,head_judge\nsecurity,strict,Evaluate security readiness,false\n",
        session=session,
    )

    versions = await list_judge_profile_versions(challenge.id, session=session)
    assert [version.version_number for version in versions] == [2, 1]
    assert versions[0].is_active is True
    assert versions[0].profile_count == 2
    assert versions[0].lock_version == 1
    assert versions[1].is_active is False
    assert versions[1].profile_count == 1
    assert versions[1].lock_version == 1


@pytest.mark.asyncio
async def test_judge_profile_version_activation_uses_optimistic_locking(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Judge profile activation lock",
        prompt="Switch active judge profile version with optimistic locking.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.1,
        risk_appetite="balanced",
        complexity_slider=0.4,
    )
    session.add(challenge)
    await session.commit()

    await register_judge_profiles_json(
        challenge.id,
        JudgeProfileRegisterJSONRequest(
            profiles=[
                JudgeProfileInput(
                    domain="ops",
                    scoring_style="balanced",
                    profile_prompt="Evaluate operational quality.",
                    head_judge=True,
                )
            ]
        ),
        session=session,
    )
    await register_judge_profiles_csv(
        challenge.id,
        "domain,scoring_style,profile_prompt,head_judge\nproduct,creative,Evaluate product strategy,false\n",
        session=session,
    )

    versions = await list_judge_profile_versions(challenge.id, session=session)
    previous_version = next(item for item in versions if item.version_number == 1)
    response = await activate_judge_profile_version(
        challenge.id,
        previous_version.id,
        JudgeProfileVersionActivateRequest(expected_lock_version=1),
        session=session,
    )
    assert response.is_active is True
    assert response.lock_version == 2

    versions_stmt: Select[tuple[JudgeProfileVersion]] = (
        select(JudgeProfileVersion)
        .where(JudgeProfileVersion.challenge_id == challenge.id)
        .order_by(JudgeProfileVersion.version_number.asc())
    )
    persisted_versions = (await session.execute(versions_stmt)).scalars().all()
    assert [version.is_active for version in persisted_versions] == [True, False]

    with pytest.raises(HTTPException) as exc_info:
        await activate_judge_profile_version(
            challenge.id,
            previous_version.id,
            JudgeProfileVersionActivateRequest(expected_lock_version=1),
            session=session,
        )
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail == "judge profile version lock mismatch"
