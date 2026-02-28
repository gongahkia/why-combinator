from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeValidationSignal:
    validator_type: str
    outcome: str
    exit_code: int | None = None


def _dependency_log_signal(dependency_log: str) -> float:
    text = dependency_log.lower()
    hard_fail_tokens = ["error", "failed", "traceback", "unsatisfied", "cannot resolve"]
    warning_tokens = ["warning", "deprecated"]
    if any(token in text for token in hard_fail_tokens):
        return 0.0
    if any(token in text for token in warning_tokens):
        return 0.6
    return 1.0 if text.strip() else 0.5


def score_feasibility(
    runtime_signals: list[RuntimeValidationSignal],
    dependency_resolution_log: str,
) -> float:
    if not runtime_signals:
        runtime_score = 0.0
    else:
        passed = sum(1 for signal in runtime_signals if signal.outcome == "passed")
        failed = sum(1 for signal in runtime_signals if signal.outcome == "failed")
        skipped = sum(1 for signal in runtime_signals if signal.outcome == "skipped")
        runtime_score = (passed + (0.25 * skipped)) / max(1, passed + failed + skipped)

    dependency_score = _dependency_log_signal(dependency_resolution_log)
    feasibility_score = (0.7 * runtime_score) + (0.3 * dependency_score)
    return round(max(0.0, min(1.0, feasibility_score)), 6)
