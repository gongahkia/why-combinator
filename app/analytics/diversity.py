from __future__ import annotations

import math
import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SubmissionState
from app.db.models import Artifact, Submission
from app.scoring.similarity import build_submission_similarity_vector


def _cosine_distance(left: list[float], right: list[float]) -> float:
    dot = sum(x * y for x, y in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(x * x for x in left)) or 1.0
    right_norm = math.sqrt(sum(y * y for y in right)) or 1.0
    similarity = dot / (left_norm * right_norm)
    similarity = max(0.0, min(1.0, similarity))
    return 1.0 - similarity


async def compute_run_diversity_index(session: AsyncSession, run_id: uuid.UUID) -> float:
    submission_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == run_id,
        Submission.state == SubmissionState.ACCEPTED,
    )
    submissions = (await session.execute(submission_stmt)).scalars().all()
    if len(submissions) < 2:
        return 0.0

    vectors: list[list[float]] = []
    for submission in submissions:
        artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission.id)
        artifacts = (await session.execute(artifact_stmt)).scalars().all()
        vectors.append(
            build_submission_similarity_vector(
                summary=submission.summary,
                artifact_hashes=[artifact.content_hash for artifact in artifacts],
            )
        )

    distances: list[float] = []
    for left_index in range(len(vectors)):
        for right_index in range(left_index + 1, len(vectors)):
            distances.append(_cosine_distance(vectors[left_index], vectors[right_index]))
    return round(sum(distances) / len(distances), 6)
