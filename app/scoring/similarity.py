from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, Submission


def _hash_embedding(text: str, dimensions: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [digest[index % len(digest)] / 255.0 for index in range(dimensions)]
    magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / magnitude for value in values]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimensions")
    return max(0.0, min(1.0, sum(x * y for x, y in zip(left, right, strict=True))))


def build_submission_similarity_vector(summary: str, artifact_hashes: list[str]) -> list[float]:
    summary_vector = _hash_embedding(summary)
    artifacts_vector = _hash_embedding("::".join(sorted(artifact_hashes)) or "no_artifacts")
    return [(summary_component + artifact_component) / 2.0 for summary_component, artifact_component in zip(summary_vector, artifacts_vector, strict=True)]


@dataclass(frozen=True)
class SimilarityScore:
    submission_id: uuid.UUID
    max_similarity: float
    compared_submissions: int


async def score_submission_similarity(session: AsyncSession, submission_id: uuid.UUID) -> SimilarityScore:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("submission not found")

    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission_id)
    current_artifacts = (await session.execute(artifact_stmt)).scalars().all()
    current_vector = build_submission_similarity_vector(
        summary=submission.summary,
        artifact_hashes=[artifact.content_hash for artifact in current_artifacts],
    )

    peer_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == submission.run_id,
        Submission.id != submission_id,
    )
    peers = (await session.execute(peer_stmt)).scalars().all()
    if not peers:
        return SimilarityScore(submission_id=submission_id, max_similarity=0.0, compared_submissions=0)

    max_similarity = 0.0
    for peer in peers:
        peer_artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == peer.id)
        peer_artifacts = (await session.execute(peer_artifact_stmt)).scalars().all()
        peer_vector = build_submission_similarity_vector(
            summary=peer.summary,
            artifact_hashes=[artifact.content_hash for artifact in peer_artifacts],
        )
        max_similarity = max(max_similarity, cosine_similarity(current_vector, peer_vector))

    return SimilarityScore(
        submission_id=submission_id,
        max_similarity=round(max_similarity, 6),
        compared_submissions=len(peers),
    )
