"""Error contracts for transcript cleaning."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from typing import Mapping


class TranscriptCleaningErrorCode(StrEnum):
    """Stable error codes emitted by transcript cleaning."""

    PROVIDER_REQUIRED = "provider_required"
    PROVIDER_FAILED = "provider_failed"
    INVALID_PROVIDER_RESULT = "invalid_provider_result"
    MISSING_TRANSCRIPT_TEXT = "missing_transcript_text"
    UNSUPPORTED_PROVIDER = "unsupported_provider"


class TranscriptCleaningIssueSeverity(StrEnum):
    """Issue severity for transcript cleaning."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TranscriptCleaningIssue:
    """Structured issue reported by the cleaning layer."""

    code: TranscriptCleaningErrorCode
    message: str
    severity: TranscriptCleaningIssueSeverity = TranscriptCleaningIssueSeverity.ERROR
    field: str | None = None
    details: Mapping[str, str] = dataclass_field(default_factory=dict)


__all__ = [
    "TranscriptCleaningErrorCode",
    "TranscriptCleaningIssue",
    "TranscriptCleaningIssueSeverity",
]
