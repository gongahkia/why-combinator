from __future__ import annotations

import re
import uuid

TRACE_ID_HEADER = "X-Trace-Id"
_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def ensure_trace_id(value: str | None) -> str:
    candidate = (value or "").strip()
    if candidate and _TRACE_ID_PATTERN.fullmatch(candidate):
        return candidate
    return new_trace_id()
