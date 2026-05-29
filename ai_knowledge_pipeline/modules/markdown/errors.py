"""Error contracts for Markdown generation."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from typing import Mapping


class MarkdownGenerationErrorCode(StrEnum):
    """Stable error codes emitted by Markdown generation."""

    MISSING_TITLE = "missing_title"
    MISSING_CLEANED_TEXT = "missing_cleaned_text"
    RENDER_FAILED = "render_failed"


class MarkdownGenerationIssueSeverity(StrEnum):
    """Issue severity for Markdown generation."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MarkdownGenerationIssue:
    """Structured issue reported by the Markdown generation layer."""

    code: MarkdownGenerationErrorCode
    message: str
    severity: MarkdownGenerationIssueSeverity = MarkdownGenerationIssueSeverity.ERROR
    field: str | None = None
    details: Mapping[str, str] = dataclass_field(default_factory=dict)


__all__ = [
    "MarkdownGenerationErrorCode",
    "MarkdownGenerationIssue",
    "MarkdownGenerationIssueSeverity",
]
