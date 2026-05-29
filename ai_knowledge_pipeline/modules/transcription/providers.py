"""Provider runtime abstractions.

Concrete Whisper integrations can be added here later. This module currently
contains only a structured unavailable provider for safe defaults.
"""

from __future__ import annotations

from ai_knowledge_pipeline.modules.transcription.errors import (
    TranscriptionErrorCode,
    TranscriptionIssue,
)
from ai_knowledge_pipeline.modules.transcription.interfaces import TranscriptionProvider
from ai_knowledge_pipeline.modules.transcription.types import (
    ProviderTranscriptionResult,
    TranscriptionRequest,
)


class UnavailableTranscriptionProvider(TranscriptionProvider):
    """Provider placeholder that returns a structured error."""

    name = "unavailable"

    def transcribe(
        self,
        request: TranscriptionRequest,
    ) -> ProviderTranscriptionResult:
        return ProviderTranscriptionResult(
            text="",
            issues=(
                TranscriptionIssue(
                    code=TranscriptionErrorCode.PROVIDER_REQUIRED,
                    message="A transcription provider must be injected.",
                    field="provider",
                    details={"requested_provider": request.config.provider.value},
                ),
            ),
        )


__all__ = ["UnavailableTranscriptionProvider"]
