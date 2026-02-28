from __future__ import annotations

import re


README_MAX_CHARS = 3000
README_REQUIRED_SECTIONS: dict[str, set[str]] = {
    "overview": {"overview", "summary", "introduction"},
    "setup": {"setup", "installation", "getting started"},
    "usage": {"usage", "run", "how to run"},
}


def _normalize_heading(text: str) -> str:
    compact = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", compact).strip()


def parse_markdown_headings(text: str) -> set[str]:
    headings: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading = stripped.lstrip("#").strip()
        if heading:
            headings.add(_normalize_heading(heading))
    return headings


def validate_minimum_readme_content(
    text: str,
    max_chars: int = README_MAX_CHARS,
) -> list[str]:
    normalized = text.strip()
    if not normalized or len(normalized) > max_chars:
        return [f"README artifact must be non-empty and at most {max_chars} characters"]

    headings = parse_markdown_headings(normalized)
    missing_sections: list[str] = []
    for section, aliases in README_REQUIRED_SECTIONS.items():
        if not any(alias in headings for alias in aliases):
            missing_sections.append(section)

    if not missing_sections:
        return []
    return [f"README artifact missing required sections: {', '.join(missing_sections)}"]
