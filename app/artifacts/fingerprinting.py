from __future__ import annotations

import ast
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, Submission


@dataclass(frozen=True)
class ArtifactFingerprint:
    artifact_id: uuid.UUID
    language: str
    framework: str
    dependencies: list[str]
    ast_fingerprint: list[str]


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


def _ast_shingles(tokens: list[str], width: int = 3) -> set[str]:
    if len(tokens) < width:
        return set(tokens)
    return {"::".join(tokens[index : index + width]) for index in range(len(tokens) - width + 1)}


def _python_ast_fingerprint(content: str) -> set[str]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return set()

    tokens: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AST):
            tokens.append(type(node).__name__)
    return _ast_shingles(tokens)


def _javascript_ast_fingerprint(content: str) -> set[str]:
    structural_tokens = re.findall(
        r"\b(?:function|class|if|else|for|while|switch|case|return|import|export|try|catch|async|await|const|let|var)\b|[{}()[\]]",
        content,
        flags=re.IGNORECASE,
    )
    normalized = [token.lower() for token in structural_tokens]
    return _ast_shingles(normalized)


def _extract_ast_fingerprint(path: Path, content: str) -> set[str]:
    language = _infer_language(path)
    if language == "python":
        return _python_ast_fingerprint(content)
    if language in {"javascript", "typescript"}:
        return _javascript_ast_fingerprint(content)
    return set()


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


def _iter_artifact_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return [candidate for candidate in path.rglob("*") if candidate.is_file()]


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


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
                    ast_fingerprint=[],
                )
            )
            continue

        files = _iter_artifact_files(path)
        if not files:
            fingerprints.append(
                ArtifactFingerprint(
                    artifact_id=artifact.id,
                    language="unknown",
                    framework="unknown",
                    dependencies=[],
                    ast_fingerprint=[],
                )
            )
            continue

        languages = [_infer_language(file_path) for file_path in files]
        known_languages = sorted({language for language in languages if language != "unknown"})
        language = known_languages[0] if len(known_languages) == 1 else ("mixed" if known_languages else "unknown")

        framework = "unknown"
        dependencies: set[str] = set()
        ast_fingerprint: set[str] = set()
        for file_path in files:
            content = _read_text_file(file_path)
            if framework == "unknown":
                framework = _infer_framework(file_path, content)
            dependencies.update(_extract_dependencies(file_path, content))
            ast_fingerprint.update(_extract_ast_fingerprint(file_path, content))

        fingerprints.append(
            ArtifactFingerprint(
                artifact_id=artifact.id,
                language=language,
                framework=framework,
                dependencies=sorted(dependencies),
                ast_fingerprint=sorted(ast_fingerprint),
            )
        )
    return fingerprints


def ast_fingerprint_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return round(len(left & right) / len(union), 6)


async def score_submission_ast_similarity(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
) -> tuple[float, uuid.UUID | None]:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("submission not found")

    current_fingerprints = await fingerprint_submission_artifacts(session, submission_id, storage_root)
    current_ast_fingerprint: set[str] = set()
    for fingerprint in current_fingerprints:
        current_ast_fingerprint.update(fingerprint.ast_fingerprint)

    peer_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == submission.run_id,
        Submission.id != submission_id,
    )
    peers = (await session.execute(peer_stmt)).scalars().all()
    if not peers:
        return 0.0, None

    best_similarity = 0.0
    best_peer_id: uuid.UUID | None = None
    for peer in peers:
        peer_fingerprints = await fingerprint_submission_artifacts(session, peer.id, storage_root)
        peer_ast_fingerprint: set[str] = set()
        for fingerprint in peer_fingerprints:
            peer_ast_fingerprint.update(fingerprint.ast_fingerprint)

        similarity = ast_fingerprint_similarity(current_ast_fingerprint, peer_ast_fingerprint)
        if similarity > best_similarity:
            best_similarity = similarity
            best_peer_id = peer.id

    return round(best_similarity, 6), best_peer_id
