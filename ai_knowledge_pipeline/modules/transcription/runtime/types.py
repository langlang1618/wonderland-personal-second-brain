"""Typed contracts for local transcription runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ai_knowledge_pipeline.modules.transcription.types import TranscriptArtifact


class FasterWhisperModelSize(StrEnum):
    """Supported faster-whisper model sizes."""

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"


@dataclass(frozen=True, slots=True)
class FasterWhisperConfig:
    """Configuration for faster-whisper runtime."""

    model_size: FasterWhisperModelSize = FasterWhisperModelSize.SMALL
    language: str | None = "zh"
    device: str = "auto"
    compute_type: str = "default"


@dataclass(frozen=True, slots=True)
class ChunkTranscriptArtifact:
    """Runtime wrapper for one chunk transcript text file."""

    transcript: TranscriptArtifact
    text_path: Path
    metadata: dict[str, str] = field(default_factory=dict)


__all__ = [
    "ChunkTranscriptArtifact",
    "FasterWhisperConfig",
    "FasterWhisperModelSize",
]
