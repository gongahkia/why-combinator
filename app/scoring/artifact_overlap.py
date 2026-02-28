from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, Submission


def _hash_shingles(content_hashes: list[str], shingle_size: int = 8) -> set[str]:
    shingles: set[str] = set()
    for content_hash in sorted(content_hashes):
        if len(content_hash) <= shingle_size:
            shingles.add(content_hash)
            continue
        for index in range(len(content_hash) - shingle_size + 1):
            shingles.add(content_hash[index : index + shingle_size])
    return shingles


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    intersection = left & right
    return len(intersection) / len(union) if union else 0.0


def _extract_dependency_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    filename = path.name.lower()
    if filename == "package.json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return set()
        dependencies = payload.get("dependencies", {})
        dev_dependencies = payload.get("devDependencies", {})
        return set(dependencies.keys()) | set(dev_dependencies.keys())
    if filename in {"requirements.txt", "constraints.txt"}:
        names: set[str] = set()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            names.add(stripped.split("==")[0].split(">=")[0].split("<=")[0].strip())
        return names
    if filename == "pyproject.toml":
        text = path.read_text(encoding="utf-8", errors="ignore")
        names: set[str] = set()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('"') and ("==" in stripped or ">=" in stripped or "<=" in stripped):
                names.add(stripped.split("==")[0].split(">=")[0].split("<=")[0].strip('" '))
        return names
    return set()


def _dependency_signature(artifacts: list[Artifact], storage_root: Path) -> set[str]:
    dependencies: set[str] = set()
    for artifact in artifacts:
        artifact_path = storage_root / artifact.storage_key
        dependencies.update(_extract_dependency_names(artifact_path))
    return dependencies


def _dependency_overlap(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / len(left | right)


@dataclass(frozen=True)
class ArtifactOverlapScore:
    submission_id: uuid.UUID
    max_overlap: float
    compared_submissions: int


async def score_artifact_overlap(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
) -> ArtifactOverlapScore:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("submission not found")

    current_artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission_id)
    current_artifacts = (await session.execute(current_artifact_stmt)).scalars().all()
    current_shingles = _hash_shingles([artifact.content_hash for artifact in current_artifacts])
    root = Path(storage_root)
    current_dependencies = _dependency_signature(current_artifacts, root)

    peer_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == submission.run_id,
        Submission.id != submission_id,
    )
    peers = (await session.execute(peer_stmt)).scalars().all()
    if not peers:
        return ArtifactOverlapScore(submission_id=submission_id, max_overlap=0.0, compared_submissions=0)

    max_overlap = 0.0
    for peer in peers:
        peer_artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == peer.id)
        peer_artifacts = (await session.execute(peer_artifact_stmt)).scalars().all()
        peer_shingles = _hash_shingles([artifact.content_hash for artifact in peer_artifacts])
        peer_dependencies = _dependency_signature(peer_artifacts, root)

        shingle_score = _jaccard_similarity(current_shingles, peer_shingles)
        dependency_score = _dependency_overlap(current_dependencies, peer_dependencies)
        overlap = (shingle_score + dependency_score) / 2.0
        max_overlap = max(max_overlap, overlap)

    return ArtifactOverlapScore(
        submission_id=submission_id,
        max_overlap=round(max_overlap, 6),
        compared_submissions=len(peers),
    )
