"""Protocol boundaries for transcript cleaning."""

from __future__ import annotations

from typing import Protocol

from ai_knowledge_pipeline.modules.cleaning.types import (
    CleaningProviderResult,
    TranscriptCleaningRequest,
    TranscriptCleaningResult,
)


class TranscriptCleaningProvider(Protocol):
    """Boundary implemented by concrete LLM cleaning providers."""

    name: str

    def clean(self, request: TranscriptCleaningRequest) -> CleaningProviderResult:
        """Clean and structure one raw transcript artifact."""


class TranscriptCleaner(Protocol):
    """Top-level transcript cleaning orchestration boundary."""

    def clean(self, request: TranscriptCleaningRequest) -> TranscriptCleaningResult:
        """Convert a TranscriptArtifact into a CleanedTranscriptArtifact."""


__all__ = ["TranscriptCleaner", "TranscriptCleaningProvider"]
