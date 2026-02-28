from __future__ import annotations

from pydantic import BaseModel


class APIErrorModel(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


VALIDATION_ERROR = {
    "model": APIErrorModel,
    "description": "Validation error",
    "content": {
        "application/json": {
            "example": {"code": "validation", "message": "Request validation failed", "details": {"field": "reason"}}
        }
    },
}

BUDGET_EXHAUSTED_ERROR = {
    "model": APIErrorModel,
    "description": "Budget exhausted",
    "content": {"application/json": {"example": {"code": "budget_exhausted", "message": "Run budget exhausted"}}},
}

SANDBOX_FAILURE_ERROR = {
    "model": APIErrorModel,
    "description": "Sandbox failure",
    "content": {"application/json": {"example": {"code": "sandbox_failure", "message": "Sandbox execution failed"}}},
}

SCORING_UNAVAILABLE_ERROR = {
    "model": APIErrorModel,
    "description": "Scoring unavailable",
    "content": {
        "application/json": {"example": {"code": "scoring_unavailable", "message": "Scoring backend temporarily unavailable"}}
    },
}
