from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JudgeProfile

DEFAULT_JUDGE_PANEL: list[tuple[str, str, str]] = [
    ("domain_expert", "strict", "Domain expert judge focused on core solution quality."),
    ("engineering", "balanced", "Engineering judge focused on feasibility and implementation quality."),
    ("product", "balanced", "Product judge focused on user value and clarity."),
]


REGULATED_KEYWORDS = {
    "hipaa",
    "healthcare",
    "medical",
    "gdpr",
    "pci",
    "sox",
    "banking",
    "finance",
    "fintech",
    "legal",
    "compliance",
}


def _needs_compliance_judge(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(keyword in lowered for keyword in REGULATED_KEYWORDS)


async def seed_default_judge_panel_if_incomplete(
    session: AsyncSession,
    challenge_id: uuid.UUID,
    challenge_prompt: str,
) -> list[JudgeProfile]:
    stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(JudgeProfile.challenge_id == challenge_id)
    existing = (await session.execute(stmt)).scalars().all()
    existing_domains = {profile.domain for profile in existing}

    created: list[JudgeProfile] = []
    for domain, scoring_style, profile_prompt in DEFAULT_JUDGE_PANEL:
        if domain in existing_domains:
            continue
        row = JudgeProfile(
            challenge_id=challenge_id,
            domain=domain,
            scoring_style=scoring_style,
            profile_prompt=profile_prompt,
            head_judge=(domain == "domain_expert"),
            source_type="bootstrap_default",
        )
        session.add(row)
        created.append(row)
    if created:
        await session.flush()

    if "compliance" not in existing_domains and _needs_compliance_judge(challenge_prompt):
        compliance_row = JudgeProfile(
            challenge_id=challenge_id,
            domain="compliance",
            scoring_style="strict",
            profile_prompt="Compliance judge focused on regulatory and safety requirements.",
            head_judge=False,
            source_type="auto_suggestion",
        )
        session.add(compliance_row)
        created.append(compliance_row)
        await session.flush()
    return created
