from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JudgeProfile


class RunStartValidationError(Exception):
    pass


async def validate_domain_expert_judge_present(session: AsyncSession, challenge_id: uuid.UUID) -> None:
    stmt: Select[tuple[int]] = select(func.count()).select_from(JudgeProfile).where(
        JudgeProfile.challenge_id == challenge_id,
        func.lower(JudgeProfile.domain) == "domain_expert",
    )
    domain_expert_count = (await session.execute(stmt)).scalar_one()
    if domain_expert_count < 1:
        raise RunStartValidationError(
            "challenge must have at least one judge profile with domain 'domain_expert' before run start"
        )
