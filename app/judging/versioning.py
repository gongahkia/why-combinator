from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JudgeProfile, JudgeProfileVersion


def serialize_judge_profile(profile: JudgeProfile) -> dict[str, object]:
    return {
        "domain": profile.domain,
        "scoring_style": profile.scoring_style,
        "profile_prompt": profile.profile_prompt,
        "head_judge": profile.head_judge,
        "source_type": profile.source_type,
    }


async def create_judge_profile_version_snapshot(
    session: AsyncSession,
    challenge_id: uuid.UUID,
    *,
    activate: bool = True,
) -> JudgeProfileVersion:
    profiles_stmt: Select[tuple[JudgeProfile]] = (
        select(JudgeProfile)
        .where(JudgeProfile.challenge_id == challenge_id)
        .order_by(JudgeProfile.created_at.asc(), JudgeProfile.id.asc())
    )
    profiles = (await session.execute(profiles_stmt)).scalars().all()
    payload = [serialize_judge_profile(profile) for profile in profiles]

    latest_version_stmt: Select[tuple[int | None]] = select(func.max(JudgeProfileVersion.version_number)).where(
        JudgeProfileVersion.challenge_id == challenge_id
    )
    latest_version = (await session.execute(latest_version_stmt)).scalar_one()
    next_version_number = (latest_version or 0) + 1

    if activate:
        await session.execute(
            update(JudgeProfileVersion)
            .where(JudgeProfileVersion.challenge_id == challenge_id)
            .values(is_active=False)
        )

    row = JudgeProfileVersion(
        challenge_id=challenge_id,
        version_number=next_version_number,
        is_active=activate,
        lock_version=1,
        profiles_payload=payload,
    )
    session.add(row)
    await session.flush()
    return row
