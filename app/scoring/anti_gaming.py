from __future__ import annotations

import difflib
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.fingerprinting import score_submission_ast_similarity
from app.db.models import Submission


@dataclass(frozen=True)
class AntiGamingScore:
    submission_id: uuid.UUID
    penalty: float
    matched_submission_id: uuid.UUID | None
    compared_submissions: int


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens and not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _shallow_mutation_similarity(left: str, right: str) -> float:
    ratio = difflib.SequenceMatcher(a=left, b=right).ratio()
    jaccard = _token_jaccard(left, right)
    return round((0.6 * ratio) + (0.4 * jaccard), 6)


async def detect_template_clone_penalty(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str | None = None,
) -> AntiGamingScore:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("submission not found")

    current_text = _normalize_text(f"{submission.summary} {submission.value_hypothesis}")
    peer_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == submission.run_id,
        Submission.id != submission_id,
    )
    peers = (await session.execute(peer_stmt)).scalars().all()
    if not peers:
        return AntiGamingScore(
            submission_id=submission_id,
            penalty=0.0,
            matched_submission_id=None,
            compared_submissions=0,
        )

    best_text_similarity = 0.0
    best_text_peer_id: uuid.UUID | None = None
    for peer in peers:
        peer_text = _normalize_text(f"{peer.summary} {peer.value_hypothesis}")
        similarity = _shallow_mutation_similarity(current_text, peer_text)
        if similarity > best_text_similarity:
            best_text_similarity = similarity
            best_text_peer_id = peer.id

    best_ast_similarity = 0.0
    best_ast_peer_id: uuid.UUID | None = None
    if storage_root:
        best_ast_similarity, best_ast_peer_id = await score_submission_ast_similarity(
            session,
            submission_id=submission_id,
            storage_root=storage_root,
        )

    if best_ast_similarity >= best_text_similarity:
        best_similarity = best_ast_similarity
        best_peer_id = best_ast_peer_id
    else:
        best_similarity = best_text_similarity
        best_peer_id = best_text_peer_id

    # Penalize only high overlap (textual or AST structural) to target shallow template mutations.
    penalty = best_similarity if best_similarity >= 0.85 else 0.0
    return AntiGamingScore(
        submission_id=submission_id,
        penalty=round(penalty, 6),
        matched_submission_id=best_peer_id if penalty > 0 else None,
        compared_submissions=len(peers),
    )
