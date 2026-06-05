"""Runtime transcription error helpers."""

from __future__ import annotations

from ai_knowledge_pipeline.modules.transcription.errors import (
    TranscriptionErrorCode,
    TranscriptionIssue,
)


def transcription_issue(
    code: TranscriptionErrorCode,
    message: str,
    field: str,
    details=None,
) -> TranscriptionIssue:
    """Create a structured transcription issue."""

    return TranscriptionIssue(
        code=code,
        message=message,
        field=field,
        details=details or {},
    )


__all__ = ["transcription_issue"]
