from __future__ import annotations

import csv
import io
import json

import yaml


class ProfileParseError(ValueError):
    pass



def _parse_csv(text: str) -> list[dict[str, object]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ProfileParseError("csv payload is missing headers")

    required = {"domain", "scoring_style", "profile_prompt"}
    if not required.issubset(set(reader.fieldnames)):
        raise ProfileParseError("csv payload missing required headers")

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
        raise ProfileParseError("payload must be UTF-8") from exc

    stripped = text.lstrip()

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return "json", json.loads(text)
        except json.JSONDecodeError:
            pass

    if "domain" in text and "," in text and "\n" in text:
        try:
            return "csv", _parse_csv(text)
        except ProfileParseError:
            pass

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProfileParseError(f"unable to parse payload: {exc}") from exc

    if parsed is None:
        raise ProfileParseError("payload is empty")
    return "yaml", parsed
