"""Typed contracts for the transcription layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypeAlias

from ai_knowledge_pipeline.core.artifact import ArtifactSnapshot
from ai_knowledge_pipeline.core.runtime import JobId, RunId, StageId, TaskId
from ai_knowledge_pipeline.core.source import MetadataMap, SourceId
from ai_knowledge_pipeline.modules.chunking.types import MediaChunkArtifact
from ai_knowledge_pipeline.modules.transcription.errors import (
    TranscriptionIssue,
    TranscriptionIssueSeverity,
)


TranscriptArtifactId: TypeAlias = str
TranscriptSeconds: TypeAlias = float
SpeakerId: TypeAlias = str


class TranscriptionProviderKind(StrEnum):
    """Supported future provider families."""

    OPENAI_WHISPER = "openai_whisper"
    FASTER_WHISPER = "faster_whisper"
    WHISPER_CPP = "whisper_cpp"
    WHISPER_KIT = "whisper_kit"
    GROQ_WHISPER = "groq_whisper"
    LOCAL_WHISPER = "local_whisper"
    MOCK = "mock"


class TranscriptionStatus(StrEnum):
    """Lifecycle status for transcript outputs."""

    PLANNED = "planned"
    TRANSCRIBED = "transcribed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TranscriptFormat(StrEnum):
    """Transcript artifact text format."""

    PLAIN_TEXT = "plain_text"
    JSON = "json"
    SRT = "srt"
    VTT = "vtt"


@dataclass(frozen=True, slots=True)
class TranscriptTimestamp:
    """Timestamp range in seconds."""

    start_time: TranscriptSeconds
    end_time: TranscriptSeconds

    @property
    def duration(self) -> TranscriptSeconds:
        """Return timestamp duration."""

        return self.end_time - self.start_time


@dataclass(frozen=True, slots=True)
class SpeakerMetadata:
    """Future-compatible speaker metadata."""

    speaker_id: SpeakerId | None = None
    label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """One timestamped transcript segment."""

    segment_index: int
    timestamp: TranscriptTimestamp
    text: str
    confidence: float | None = None
    speaker: SpeakerMetadata | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranscriptionConfig:
    """Configuration knobs for transcription."""

    raw_transcripts_dir: Path = Path("data/transcripts/raw")
    provider: TranscriptionProviderKind = TranscriptionProviderKind.MOCK
    transcript_format: TranscriptFormat = TranscriptFormat.JSON
    language: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    local_transcript_path: Path | None = None


@dataclass(frozen=True, slots=True)
class TranscriptionRequest:
    """Input to the transcription layer."""

    chunk: MediaChunkArtifact
    config: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId = "transcription"
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderTranscriptionResult:
    """Provider output before artifact materialization."""

    text: str
    segments: tuple[TranscriptSegment, ...] = ()
    language: str | None = None
    confidence: float | None = None
    model_name: str | None = None
    metadata: MetadataMap = field(default_factory=dict)
    issues: tuple[TranscriptionIssue, ...] = ()

    @property
    def is_success(self) -> bool:
        """Return whether provider output contains text and no errors."""

        return bool(self.text) and not any(
            issue.severity is TranscriptionIssueSeverity.ERROR
            for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class TranscriptArtifact:
    """Unified transcript artifact emitted by transcription."""

    transcript_artifact_id: TranscriptArtifactId
    source_id: SourceId
    parent_chunk_artifact_id: str
    chunk_index: int
    status: TranscriptionStatus
    text: str
    segments: tuple[TranscriptSegment, ...]
    language: str | None
    confidence: float | None
    path: Path | None
    uri: str
    snapshot: ArtifactSnapshot
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Top-level output of the transcription layer."""

    transcript: TranscriptArtifact | None
    status: TranscriptionStatus
    issues: tuple[TranscriptionIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Return whether transcription produced an artifact."""

        return self.transcript is not None and not any(
            issue.severity is TranscriptionIssueSeverity.ERROR
            for issue in self.issues
        )


__all__ = [
    "ProviderTranscriptionResult",
    "SpeakerId",
    "SpeakerMetadata",
    "TranscriptArtifact",
    "TranscriptArtifactId",
    "TranscriptFormat",
    "TranscriptSeconds",
    "TranscriptSegment",
    "TranscriptTimestamp",
    "TranscriptionConfig",
    "TranscriptionProviderKind",
    "TranscriptionRequest",
    "TranscriptionResult",
    "TranscriptionStatus",
]
