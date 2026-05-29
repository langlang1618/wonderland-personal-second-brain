"""Error contracts for source normalization.

The sources layer should report structured errors instead of leaking parser or
filesystem implementation details into orchestration code.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from typing import Mapping


class SourceErrorCode(StrEnum):
    """Stable error codes emitted by the sources layer."""

    UNSUPPORTED_INPUT = "unsupported_input"
    AMBIGUOUS_INPUT = "ambiguous_input"
    REMOTE_SOURCES_DISABLED = "remote_sources_disabled"
    LOCAL_SOURCES_DISABLED = "local_sources_disabled"
    INVALID_URL = "invalid_url"
    INVALID_LOCAL_PATH = "invalid_local_path"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    MISSING_REQUIRED_METADATA = "missing_required_metadata"
    MANIFEST_WRITE_FAILED = "manifest_write_failed"
    MANIFEST_READ_FAILED = "manifest_read_failed"


class SourceIssueSeverity(StrEnum):
    """Severity for parser and validator issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SourceIssue:
    """A non-throwing issue reported during detection, parsing, or validation."""

    code: SourceErrorCode
    message: str
    severity: SourceIssueSeverity = SourceIssueSeverity.ERROR
    field: str | None = None
    details: Mapping[str, str] = dataclass_field(default_factory=dict)


class SourceNormalizationError(Exception):
    """Base exception for future source normalization implementations."""

    def __init__(self, issue: SourceIssue) -> None:
        super().__init__(issue.message)
        self.issue = issue


__all__ = [
    "SourceErrorCode",
    "SourceIssue",
    "SourceIssueSeverity",
    "SourceNormalizationError",
]
