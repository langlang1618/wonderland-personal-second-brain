"""Error contracts for the media download layer."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from typing import Mapping


class MediaDownloadErrorCode(StrEnum):
    """Stable error codes emitted by the download layer."""

    UNSUPPORTED_SOURCE_KIND = "unsupported_source_kind"
    ADAPTER_REQUIRED = "adapter_required"
    ADAPTER_FAILED = "adapter_failed"
    SUBPROCESS_FAILED = "subprocess_failed"
    SUBPROCESS_TIMEOUT = "subprocess_timeout"
    EXECUTABLE_NOT_FOUND = "executable_not_found"
    INVALID_SOURCE_LOCATION = "invalid_source_location"
    DOWNLOAD_SKIPPED = "download_skipped"
    OUTPUT_PATH_UNAVAILABLE = "output_path_unavailable"


class MediaDownloadIssueSeverity(StrEnum):
    """Issue severity for download planning and execution."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MediaDownloadIssue:
    """Structured issue reported by the download layer."""

    code: MediaDownloadErrorCode
    message: str
    severity: MediaDownloadIssueSeverity = MediaDownloadIssueSeverity.ERROR
    field: str | None = None
    details: Mapping[str, str] = dataclass_field(default_factory=dict)


__all__ = [
    "MediaDownloadErrorCode",
    "MediaDownloadIssue",
    "MediaDownloadIssueSeverity",
]
