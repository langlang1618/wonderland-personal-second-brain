"""Error contracts for transcription."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from typing import Mapping


class TranscriptionErrorCode(StrEnum):
    """Stable error codes emitted by transcription."""

    MISSING_CHUNK_PATH = "missing_chunk_path"
    PROVIDER_REQUIRED = "provider_required"
    PROVIDER_FAILED = "provider_failed"
    INVALID_PROVIDER_RESULT = "invalid_provider_result"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    MISSING_TRANSCRIPT_FILE = "missing_transcript_file"
    UNSUPPORTED_TRANSCRIPT_FORMAT = "unsupported_transcript_format"
    TRANSCRIPT_PARSE_FAILED = "transcript_parse_failed"
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_LOAD_FAILED = "model_load_failed"
    AUDIO_TRANSCRIPTION_FAILED = "audio_transcription_failed"


class TranscriptionIssueSeverity(StrEnum):
    """Issue severity for transcription."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TranscriptionIssue:
    """Structured issue reported by the transcription layer."""

    code: TranscriptionErrorCode
    message: str
    severity: TranscriptionIssueSeverity = TranscriptionIssueSeverity.ERROR
    field: str | None = None
    details: Mapping[str, str] = dataclass_field(default_factory=dict)


__all__ = [
    "TranscriptionErrorCode",
    "TranscriptionIssue",
    "TranscriptionIssueSeverity",
]
