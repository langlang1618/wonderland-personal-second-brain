"""Error contracts for Obsidian writing."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from typing import Mapping


class ObsidianWriteErrorCode(StrEnum):
    """Stable error codes emitted by Obsidian writer."""

    MISSING_VAULT_PATH = "missing_vault_path"
    EMPTY_MARKDOWN = "empty_markdown"
    WRITE_FAILED = "write_failed"
    SKIPPED_EXISTING = "skipped_existing"


class ObsidianWriteIssueSeverity(StrEnum):
    """Issue severity for Obsidian writing."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ObsidianWriteIssue:
    """Structured issue reported by the Obsidian writer."""

    code: ObsidianWriteErrorCode
    message: str
    severity: ObsidianWriteIssueSeverity = ObsidianWriteIssueSeverity.ERROR
    field: str | None = None
    details: Mapping[str, str] = dataclass_field(default_factory=dict)


__all__ = [
    "ObsidianWriteErrorCode",
    "ObsidianWriteIssue",
    "ObsidianWriteIssueSeverity",
]
