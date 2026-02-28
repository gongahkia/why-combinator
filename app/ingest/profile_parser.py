from __future__ import annotations

import csv
import io
import json

import yaml


class ProfileParseError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        source_format: str | None = None,
        line: int | None = None,
        column: int | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.source_format = source_format
        self.line = line
        self.column = column
        self.reason = reason

    def as_payload(self) -> dict[str, object]:
        return {
            "message": self.message,
            "source_format": self.source_format,
            "line": self.line,
            "column": self.column,
            "reason": self.reason,
        }



def _parse_csv(text: str) -> list[dict[str, object]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ProfileParseError("csv payload is missing headers", source_format="csv")

    required = {"domain", "scoring_style", "profile_prompt"}
    if not required.issubset(set(reader.fieldnames)):
        missing = sorted(required - set(reader.fieldnames))
        raise ProfileParseError(
            "csv payload missing required headers",
            source_format="csv",
            reason=f"missing headers: {', '.join(missing)}",
        )

    rows: list[dict[str, object]] = []
    for row in reader:
        rows.append(
            {
                "domain": (row.get("domain") or "").strip(),
                "scoring_style": (row.get("scoring_style") or "").strip(),
                "profile_prompt": (row.get("profile_prompt") or "").strip(),
                "head_judge": str(row.get("head_judge", "")).strip().lower() in {"1", "true", "yes", "y"},
            }
        )
    return rows



def parse_profile_payload(content: bytes) -> tuple[str, object]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileParseError("payload must be UTF-8", reason=str(exc)) from exc

    stripped = text.lstrip()

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return "json", json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProfileParseError(
                "invalid json payload",
                source_format="json",
                line=exc.lineno,
                column=exc.colno,
                reason=exc.msg,
            ) from exc

    if "domain" in text and "," in text and "\n" in text:
        return "csv", _parse_csv(text)

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        column = getattr(getattr(exc, "problem_mark", None), "column", None)
        raise ProfileParseError(
            "invalid yaml payload",
            source_format="yaml",
            line=None if line is None else int(line) + 1,
            column=None if column is None else int(column) + 1,
            reason=str(exc),
        ) from exc

    if parsed is None:
        raise ProfileParseError("payload is empty", source_format="yaml")
    return "yaml", parsed
