from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.api.judges import register_judge_profiles_bulk
from app.db.models import Challenge, JudgeProfile


@pytest.mark.asyncio
async def test_bulk_judge_profile_import_accepts_mixed_json_yaml_csv(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Mixed bulk judge import",
        prompt="Import judge panel definitions from mixed formats.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.2,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.commit()

    files = [
        UploadFile(
            filename="panel.json",
            file=BytesIO(
                (
                    '{"profiles":[{"domain":"ops","scoring_style":"balanced",'
                    '"profile_prompt":"Evaluate execution reliability.","head_judge":true}]}'
                ).encode("utf-8")
            ),
        ),
        UploadFile(
            filename="panel.yaml",
            file=BytesIO(
                (
                    "- domain: finance\n"
                    "  scoring_style: strict\n"
                    "  profile_prompt: Evaluate cost and profitability.\n"
                    "  head_judge: false\n"
                ).encode("utf-8")
            ),
        ),
        UploadFile(
            filename="panel.csv",
            file=BytesIO(
                (
                    "domain,scoring_style,profile_prompt,head_judge\n"
                    "security,creative,Evaluate security posture,false\n"
                ).encode("utf-8")
            ),
        ),
    ]

    response = await register_judge_profiles_bulk(challenge.id, files=files, session=session)

    assert len(response) == 3
    assert {item.source_type for item in response} == {"bulk_json", "bulk_yaml", "bulk_csv"}
    assert {item.domain for item in response} == {"ops", "finance", "security"}
    assert sum(1 for item in response if item.head_judge) == 1

    profiles_stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(JudgeProfile.challenge_id == challenge.id)
    profiles = (await session.execute(profiles_stmt)).scalars().all()
    assert len(profiles) == 3


@pytest.mark.asyncio
async def test_bulk_judge_profile_import_rejects_multiple_head_judges_across_files(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Bulk head judge conflict",
        prompt="Reject conflicting head judges in bulk import.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.2,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.commit()

    files = [
        UploadFile(
            filename="head.json",
            file=BytesIO(
                (
                    '{"profiles":[{"domain":"ops","scoring_style":"balanced",'
                    '"profile_prompt":"Evaluate execution reliability.","head_judge":true}]}'
                ).encode("utf-8")
            ),
        ),
        UploadFile(
            filename="head.yaml",
            file=BytesIO(
                (
                    "- domain: finance\n"
                    "  scoring_style: strict\n"
                    "  profile_prompt: Evaluate cost and profitability.\n"
                    "  head_judge: true\n"
                ).encode("utf-8")
            ),
        ),
    ]

    with pytest.raises(HTTPException) as exc_info:
        await register_judge_profiles_bulk(challenge.id, files=files, session=session)

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail == "at most one head_judge is allowed per challenge panel"

    profiles_stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(JudgeProfile.challenge_id == challenge.id)
    profiles = (await session.execute(profiles_stmt)).scalars().all()
    assert profiles == []
