#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import load_settings
from app.db.models import Challenge
from app.orchestrator.judge_bootstrap import seed_default_judge_panel_if_incomplete


@dataclass(frozen=True)
class ChallengeTemplate:
    title: str
    prompt: str
    iteration_window_seconds: int
    minimum_quality_threshold: float
    risk_appetite: str
    complexity_slider: float


DEFAULT_CHALLENGE_TEMPLATES: list[ChallengeTemplate] = [
    ChallengeTemplate(
        title="Retail Demand Forecaster MVP",
        prompt=(
            "Build an MVP that predicts daily product demand per store using historical sales and promotions, "
            "with a simple UI for planners to inspect forecast confidence."
        ),
        iteration_window_seconds=2 * 60 * 60,
        minimum_quality_threshold=0.65,
        risk_appetite="balanced",
        complexity_slider=0.55,
    ),
    ChallengeTemplate(
        title="Healthcare Intake Copilot",
        prompt=(
            "Build a healthcare intake assistant that summarizes patient intake forms and highlights triage risks "
            "for nurse review while preserving clear auditability."
        ),
        iteration_window_seconds=90 * 60,
        minimum_quality_threshold=0.7,
        risk_appetite="conservative",
        complexity_slider=0.45,
    ),
    ChallengeTemplate(
        title="Developer Onboarding Accelerator",
        prompt=(
            "Build an engineering onboarding MVP that ingests repository docs and creates role-specific 7-day "
            "learning plans with actionable first-issue recommendations."
        ),
        iteration_window_seconds=2 * 60 * 60,
        minimum_quality_threshold=0.6,
        risk_appetite="aggressive",
        complexity_slider=0.75,
    ),
]


async def _seed(session: AsyncSession) -> tuple[int, int]:
    created = 0
    skipped = 0
    for template in DEFAULT_CHALLENGE_TEMPLATES:
        stmt: Select[tuple[Challenge]] = select(Challenge).where(Challenge.title == template.title).limit(1)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        challenge = Challenge(
            title=template.title,
            prompt=template.prompt,
            iteration_window_seconds=template.iteration_window_seconds,
            minimum_quality_threshold=template.minimum_quality_threshold,
            risk_appetite=template.risk_appetite,
            complexity_slider=template.complexity_slider,
        )
        session.add(challenge)
        await session.flush()
        await seed_default_judge_panel_if_incomplete(session, challenge.id, challenge.prompt)
        created += 1

    await session.commit()
    return created, skipped


async def _main() -> int:
    settings = load_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            created, skipped = await _seed(session)
    finally:
        await engine.dispose()

    print(f"seeded default challenges: created={created} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
