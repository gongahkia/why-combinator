from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    CANCELING = "canceling"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"


class AgentRole(StrEnum):
    HACKER = "hacker"
    SUBAGENT = "subagent"
    JUDGE = "judge"


class SubmissionState(StrEnum):
    PENDING = "pending"
    SCORED = "scored"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ArtifactType(StrEnum):
    WEB_BUNDLE = "web_bundle"
    CLI_PACKAGE = "cli_package"
    API_SERVICE = "api_service"
    NOTEBOOK = "notebook"
