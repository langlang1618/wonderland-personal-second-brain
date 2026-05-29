"""Typed contracts for the media chunking layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypeAlias

from ai_knowledge_pipeline.core.artifact import ArtifactSnapshot
from ai_knowledge_pipeline.core.runtime import JobId, RunId, StageId, TaskId
from ai_knowledge_pipeline.core.source import MetadataMap, SourceId
from ai_knowledge_pipeline.modules.chunking.errors import (
    MediaChunkingIssue,
    MediaChunkingIssueSeverity,
)
from ai_knowledge_pipeline.modules.download.types import LocalMediaArtifact


ChunkCommand: TypeAlias = tuple[str, ...]
ChunkArtifactId: TypeAlias = str
TimelineSeconds: TypeAlias = float


class MediaChunkingMode(StrEnum):
    """How chunking should handle a request."""

    MATERIALIZE = "materialize"
    DRY_RUN = "dry_run"


class MediaChunkingStatus(StrEnum):
    """Lifecycle status for chunk outputs."""

    PLANNED = "planned"
    MATERIALIZED = "materialized"
    FAILED = "failed"
    SKIPPED = "skipped"


class SegmentationStrategyKind(StrEnum):
    """Supported timeline segmentation strategy families."""

    FIXED_DURATION = "fixed_duration"
    SILENCE_DETECTION = "silence_detection"
    VAD = "vad"
    SEMANTIC = "semantic"
    SPEAKER_AWARE = "speaker_aware"


@dataclass(frozen=True, slots=True)
class MediaChunkingConfig:
    """Configuration knobs for media chunk planning."""

    chunks_dir: Path = Path("data/chunks")
    temp_dir: Path = Path("data/tmp/chunks")
    chunk_duration_seconds: float = 1800
    mode: MediaChunkingMode = MediaChunkingMode.MATERIALIZE
    ffmpeg_binary: str = "ffmpeg"
    output_extension: str = ".m4a"
    subprocess_timeout_seconds: float | None = None
    segmentation_strategy: SegmentationStrategyKind = (
        SegmentationStrategyKind.FIXED_DURATION
    )


@dataclass(frozen=True, slots=True)
class TimelineSegment:
    """One planned media timeline segment."""

    chunk_index: int
    start_time: TimelineSeconds
    end_time: TimelineSeconds

    @property
    def duration(self) -> TimelineSeconds:
        """Return segment duration."""

        return self.end_time - self.start_time


@dataclass(frozen=True, slots=True)
class MediaChunkingRequest:
    """Input to the media chunking layer."""

    media: LocalMediaArtifact
    media_duration_seconds: float | None = None
    config: MediaChunkingConfig = field(default_factory=MediaChunkingConfig)
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId = "chunking"
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaChunkPlan:
    """Pure chunking plan for one input media artifact."""

    source_id: SourceId
    parent_media_artifact_id: str
    parent_snapshot_id: str
    input_path: Path
    chunks_dir: Path
    temp_dir: Path
    segments: tuple[TimelineSegment, ...]
    commands: tuple[ChunkCommand, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaChunkArtifact:
    """Unified chunk artifact emitted by the chunking layer."""

    chunk_artifact_id: ChunkArtifactId
    source_id: SourceId
    parent_media_artifact_id: str
    chunk_index: int
    start_time: TimelineSeconds
    end_time: TimelineSeconds
    duration: TimelineSeconds
    status: MediaChunkingStatus
    path: Path | None
    uri: str
    snapshot: ArtifactSnapshot
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChunkProcessOutput:
    """Structured stdout and stderr captured from ffmpeg."""

    stdout: str = ""
    stderr: str = ""
    stdout_lines: tuple[str, ...] = ()
    stderr_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChunkProcessResult:
    """Result of executing one ffmpeg subprocess."""

    command: ChunkCommand
    returncode: int
    output: ChunkProcessOutput
    output_path: Path | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaChunkAdapterResult:
    """Result returned by a concrete chunking adapter."""

    output_paths: tuple[Path, ...]
    metadata: MetadataMap = field(default_factory=dict)
    issues: tuple[MediaChunkingIssue, ...] = ()

    @property
    def is_success(self) -> bool:
        """Return whether adapter output has no error-severity issues."""

        return bool(self.output_paths) and not any(
            issue.severity is MediaChunkingIssueSeverity.ERROR
            for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class MediaChunkingResult:
    """Top-level output of the media chunking layer."""

    chunks: tuple[MediaChunkArtifact, ...]
    plan: MediaChunkPlan | None
    status: MediaChunkingStatus
    issues: tuple[MediaChunkingIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Return whether chunking produced chunk artifacts without errors."""

        return bool(self.chunks) and not any(
            issue.severity is MediaChunkingIssueSeverity.ERROR
            for issue in self.issues
        )


__all__ = [
    "ChunkArtifactId",
    "ChunkCommand",
    "ChunkProcessOutput",
    "ChunkProcessResult",
    "MediaChunkAdapterResult",
    "MediaChunkArtifact",
    "MediaChunkPlan",
    "MediaChunkingConfig",
    "MediaChunkingMode",
    "MediaChunkingRequest",
    "MediaChunkingResult",
    "MediaChunkingStatus",
    "SegmentationStrategyKind",
    "TimelineSeconds",
    "TimelineSegment",
]
