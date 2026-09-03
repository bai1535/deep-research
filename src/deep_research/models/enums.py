"""Enums for the deep-research data model."""

from enum import StrEnum


class Perspective(StrEnum):
    TECHNICAL = "technical"
    INDUSTRY = "industry"
    CRITICAL = "critical"
    FUTURE = "future"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    SUSPECT = "suspect"
    FALSE = "false"
    DISPUTED = "disputed"


class RunStatus(StrEnum):
    PENDING = "pending"
    RESEARCHING = "researching"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"
