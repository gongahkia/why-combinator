from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact


@dataclass(frozen=True)
class ArtifactFingerprint:
    artifact_id: uuid.UUID
    language: str
    framework: str
    dependencies: list[str]


def _infer_language(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".ipynb": "python",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
    }.get(suffix, "unknown")


def _infer_framework(path: Path, content: str) -> str:
    lowered = content.lower()
    filename = path.name.lower()
    if filename == "package.json":
        if "next" in lowered:
            return "nextjs"
        if "react" in lowered:
            return "react"
        if "vue" in lowered:
            return "vue"
        if "express" in lowered:
            return "express"
    if filename == "pyproject.toml":
        if "fastapi" in lowered:
            return "fastapi"
        if "django" in lowered:
            return "django"
        if "flask" in lowered:
            return "flask"
    if filename == "requirements.txt":
        if "fastapi" in lowered:
            return "fastapi"
    return "unknown"


def _extract_dependencies(path: Path, content: str) -> list[str]:
    filename = path.name.lower()
    if filename == "package.json":
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []
        dependencies = set(payload.get("dependencies", {}).keys()) | set(payload.get("devDependencies", {}).keys())
        return sorted(str(item) for item in dependencies)
    if filename in {"requirements.txt", "constraints.txt"}:
        deps = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            deps.append(stripped.split("==")[0].split(">=")[0].split("<=")[0].strip())
        return sorted(set(deps))
    return []


async def fingerprint_submission_artifacts(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
) -> list[ArtifactFingerprint]:
    stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission_id)
    artifacts = (await session.execute(stmt)).scalars().all()

    fingerprints: list[ArtifactFingerprint] = []
    for artifact in artifacts:
        path = Path(storage_root) / artifact.storage_key
        if not path.exists():
            fingerprints.append(
                ArtifactFingerprint(
                    artifact_id=artifact.id,
                    language="unknown",
                    framework="unknown",
                    dependencies=[],
                )
            )
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        fingerprints.append(
            ArtifactFingerprint(
                artifact_id=artifact.id,
                language=_infer_language(path),
                framework=_infer_framework(path, content),
                dependencies=_extract_dependencies(path, content),
            )
        )
    return fingerprints
