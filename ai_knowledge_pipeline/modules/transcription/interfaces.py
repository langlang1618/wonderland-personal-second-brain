"""Protocol boundaries for transcription."""

from __future__ import annotations

from typing import Protocol

from ai_knowledge_pipeline.modules.transcription.types import (
    ProviderTranscriptionResult,
    TranscriptionRequest,
    TranscriptionResult,
)


class TranscriptionProvider(Protocol):
    """Boundary implemented by concrete Whisper-compatible providers."""

    name: str

    def transcribe(
        self,
        request: TranscriptionRequest,
    ) -> ProviderTranscriptionResult:
        """Transcribe one media chunk."""


class Transcriber(Protocol):
    """Top-level transcription orchestration boundary."""

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Convert one MediaChunkArtifact into a TranscriptArtifact."""


__all__ = ["Transcriber", "TranscriptionProvider"]
