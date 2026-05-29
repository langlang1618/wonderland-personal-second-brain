"""Error contracts for media chunking."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from typing import Mapping


class MediaChunkingErrorCode(StrEnum):
    """Stable error codes emitted by the chunking layer."""

    MISSING_MEDIA_PATH = "missing_media_path"
    MISSING_MEDIA_DURATION = "missing_media_duration"
    INVALID_CHUNK_DURATION = "invalid_chunk_duration"
    ADAPTER_REQUIRED = "adapter_required"
    SUBPROCESS_FAILED = "subprocess_failed"
    SUBPROCESS_TIMEOUT = "subprocess_timeout"
    EXECUTABLE_NOT_FOUND = "executable_not_found"


class MediaChunkingIssueSeverity(StrEnum):
    """Issue severity for chunk planning and execution."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MediaChunkingIssue:
    """Structured issue reported by the chunking layer."""

    code: MediaChunkingErrorCode
    message: str
    severity: MediaChunkingIssueSeverity = MediaChunkingIssueSeverity.ERROR
    field: str | None = None
    details: Mapping[str, str] = dataclass_field(default_factory=dict)


__all__ = [
    "MediaChunkingErrorCode",
    "MediaChunkingIssue",
    "MediaChunkingIssueSeverity",
]
