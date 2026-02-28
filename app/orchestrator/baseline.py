from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BaselineIdeaVector, Challenge, Run

BASELINE_IDEA_COUNT = 3
BASELINE_VECTOR_DIMENSIONS = 16


def build_codex_baseline_prompt(challenge: Challenge, count: int = BASELINE_IDEA_COUNT) -> str:
    return (
        "You are Codex, generating baseline MVP ideas for novelty calibration.\n"
        f"Challenge title: {challenge.title}\n"
        f"Challenge prompt: {challenge.prompt}\n"
        f"Risk appetite: {challenge.risk_appetite}\n"
        f"Complexity slider: {challenge.complexity_slider}\n"
        f"Return {count} concise MVP ideas as single-sentence outputs."
    )


def _make_deterministic_vector(text: str, dimensions: int = BASELINE_VECTOR_DIMENSIONS) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [digest[index % len(digest)] / 255.0 for index in range(dimensions)]
    magnitude = (sum(value * value for value in values) ** 0.5) or 1.0
    return [round(value / magnitude, 8) for value in values]


@dataclass(frozen=True)
class BaselineIdea:
    idea_index: int
    idea_text: str
    vector: list[float]


def generate_baseline_ideas(challenge: Challenge, count: int = BASELINE_IDEA_COUNT) -> tuple[str, list[BaselineIdea]]:
    prompt_template = build_codex_baseline_prompt(challenge, count=count)
    prompt_tokens = challenge.prompt.split()
    prompt_focus = " ".join(prompt_tokens[: min(10, len(prompt_tokens))]) if prompt_tokens else challenge.title
    ideas = [
        BaselineIdea(
            idea_index=index,
            idea_text=(
                f"{challenge.title} baseline idea {index + 1}: {prompt_focus} "
                f"(risk={challenge.risk_appetite}, complexity={challenge.complexity_slider:.2f})"
            ),
            vector=_make_deterministic_vector(f"{challenge.id}:{index}:{challenge.prompt}"),
        )
        for index in range(count)
    ]
    return prompt_template, ideas


async def run_baseline_idea_generator_job(session: AsyncSession, run: Run, challenge: Challenge) -> list[BaselineIdeaVector]:
    prompt_template, ideas = generate_baseline_ideas(challenge)
    rows = [
        BaselineIdeaVector(
            run_id=run.id,
            idea_index=idea.idea_index,
            idea_text=idea.idea_text,
            vector=idea.vector,
            prompt_template=prompt_template,
        )
        for idea in ideas
    ]
    session.add_all(rows)
    return rows
