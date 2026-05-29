"""Cleaning provider runtime abstractions.

Concrete OpenAI, Claude, Gemini, or local LLM integrations can be added later.
This module currently contains only a structured unavailable provider.
"""

from __future__ import annotations

from ai_knowledge_pipeline.modules.cleaning.errors import (
    TranscriptCleaningErrorCode,
    TranscriptCleaningIssue,
)
from ai_knowledge_pipeline.modules.cleaning.interfaces import TranscriptCleaningProvider
from ai_knowledge_pipeline.modules.cleaning.types import (
    CleaningProviderResult,
    TranscriptCleaningRequest,
)


class UnavailableCleaningProvider(TranscriptCleaningProvider):
    """Provider placeholder that returns a structured error."""

    name = "unavailable"

    def clean(self, request: TranscriptCleaningRequest) -> CleaningProviderResult:
        return CleaningProviderResult(
            markdown_ready=None,
            issues=(
                TranscriptCleaningIssue(
                    code=TranscriptCleaningErrorCode.PROVIDER_REQUIRED,
                    message="A transcript cleaning provider must be injected.",
                    field="provider",
                    details={"requested_provider": request.config.provider.value},
                ),
            ),
        )


__all__ = ["UnavailableCleaningProvider"]
