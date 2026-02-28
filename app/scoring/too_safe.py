from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, BaselineIdeaVector, Submission
from app.scoring.similarity import build_submission_similarity_vector, cosine_similarity


@dataclass(frozen=True)
class TooSafePenaltyScore:
    submission_id: uuid.UUID
    too_safe_penalty: float
    compared_baselines: int


async def score_too_safe_penalty(session: AsyncSession, submission_id: uuid.UUID) -> TooSafePenaltyScore:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("submission not found")

    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission_id)
    artifacts = (await session.execute(artifact_stmt)).scalars().all()
    submission_vector = build_submission_similarity_vector(
        summary=submission.summary,
        artifact_hashes=[artifact.content_hash for artifact in artifacts],
    )

    baseline_stmt: Select[tuple[BaselineIdeaVector]] = select(BaselineIdeaVector).where(
        BaselineIdeaVector.run_id == submission.run_id
    )
    baselines = (await session.execute(baseline_stmt)).scalars().all()
    if not baselines:
        return TooSafePenaltyScore(submission_id=submission_id, too_safe_penalty=0.0, compared_baselines=0)

    max_similarity = max(cosine_similarity(submission_vector, baseline.vector) for baseline in baselines)
    return TooSafePenaltyScore(
        submission_id=submission_id,
        too_safe_penalty=round(max_similarity, 6),
        compared_baselines=len(baselines),
    )
