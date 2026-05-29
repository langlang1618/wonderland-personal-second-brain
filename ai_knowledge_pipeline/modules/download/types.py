"""Typed contracts for the media download layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypeAlias

from ai_knowledge_pipeline.core.artifact import ArtifactSnapshot
from ai_knowledge_pipeline.core.runtime import JobId, RunId, StageId, TaskId
from ai_knowledge_pipeline.core.source import MetadataMap, SourceData, SourceId
from ai_knowledge_pipeline.modules.download.errors import (
    MediaDownloadIssue,
    MediaDownloadIssueSeverity,
)


DownloadAdapterName: TypeAlias = str
DownloadCommand: TypeAlias = tuple[str, ...]
MediaArtifactId: TypeAlias = str


class MediaDownloadMode(StrEnum):
    """How the downloader should handle a request."""

    MATERIALIZE = "materialize"
    DRY_RUN = "dry_run"
    METADATA_ONLY = "metadata_only"


class MediaDownloadStatus(StrEnum):
    """Lifecycle status for media download output."""

    PLANNED = "planned"
    METADATA_ONLY = "metadata_only"
    LOCAL_REFERENCE = "local_reference"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class MediaDownloadConfig:
    """Configuration knobs for media download planning."""

    media_dir: Path = Path("data/media")
    temp_dir: Path = Path("data/tmp/downloads")
    prefer_audio: bool = True
    mode: MediaDownloadMode = MediaDownloadMode.MATERIALIZE
    ytdlp_binary: str = "yt-dlp"
    output_template: str = "{source_id}.%(ext)s"
    keep_original_local_path: bool = True
    subprocess_timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class MediaDownloadRequest:
    """Input to the media download layer."""

    source: SourceData
    config: MediaDownloadConfig = field(default_factory=MediaDownloadConfig)
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId = "download"
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaDownloadPlan:
    """Pure plan for where and how media should be materialized."""

    source_id: SourceId
    adapter_name: DownloadAdapterName
    target_path: Path
    temp_path: Path
    mode: MediaDownloadMode
    command: DownloadCommand = ()
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LocalMediaArtifact:
    """Unified local media artifact emitted by the download layer."""

    media_artifact_id: MediaArtifactId
    source_id: SourceId
    status: MediaDownloadStatus
    path: Path | None
    uri: str
    snapshot: ArtifactSnapshot
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaDownloadAdapterResult:
    """Result returned by a concrete download adapter."""

    path: Path | None
    metadata: MetadataMap = field(default_factory=dict)
    issues: tuple[MediaDownloadIssue, ...] = ()

    @property
    def is_success(self) -> bool:
        """Return whether adapter output has no error-severity issues."""

        return self.path is not None and not any(
            issue.severity is MediaDownloadIssueSeverity.ERROR
            for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class DownloadProcessOutput:
    """Structured stdout and stderr captured from a subprocess."""

    stdout: str = ""
    stderr: str = ""
    stdout_lines: tuple[str, ...] = ()
    stderr_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DownloadProcessResult:
    """Result of executing a download subprocess."""

    command: DownloadCommand
    returncode: int
    output: DownloadProcessOutput
    parsed_output_path: Path | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaDownloadResult:
    """Top-level output of the media download layer."""

    artifact: LocalMediaArtifact | None
    plan: MediaDownloadPlan
    status: MediaDownloadStatus
    issues: tuple[MediaDownloadIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Return whether the download layer produced an artifact."""

        return self.artifact is not None and not any(
            issue.severity is MediaDownloadIssueSeverity.ERROR
            for issue in self.issues
        )


__all__ = [
    "DownloadAdapterName",
    "DownloadCommand",
    "DownloadProcessOutput",
    "DownloadProcessResult",
    "LocalMediaArtifact",
    "MediaArtifactId",
    "MediaDownloadAdapterResult",
    "MediaDownloadConfig",
    "MediaDownloadMode",
    "MediaDownloadPlan",
    "MediaDownloadRequest",
    "MediaDownloadResult",
    "MediaDownloadStatus",
]
