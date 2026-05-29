"""Typed contracts for Obsidian writing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypeAlias

from ai_knowledge_pipeline.core.artifact import ArtifactSnapshot
from ai_knowledge_pipeline.core.runtime import JobId, RunId, StageId, TaskId
from ai_knowledge_pipeline.core.source import MetadataMap, SourceId
from ai_knowledge_pipeline.modules.markdown.types import MarkdownArtifact
from ai_knowledge_pipeline.modules.obsidian.errors import (
    ObsidianWriteIssue,
    ObsidianWriteIssueSeverity,
)


ObsidianNoteArtifactId: TypeAlias = str


class ObsidianConflictStrategy(StrEnum):
    """How to handle existing note paths."""

    OVERWRITE = "overwrite"
    SKIP = "skip"
    VERSIONED = "versioned"


class ObsidianWriteStatus(StrEnum):
    """Lifecycle status for Obsidian write outputs."""

    WRITTEN = "written"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ObsidianWriterConfig:
    """Configuration knobs for Obsidian vault writes."""

    vault_path: Path | None = None
    root_dir: Path = Path("AI Knowledge Pipeline")
    conflict_strategy: ObsidianConflictStrategy = ObsidianConflictStrategy.VERSIONED
    file_extension: str = ".md"
    uncategorized_dir: str = "uncategorized"


@dataclass(frozen=True, slots=True)
class ObsidianWriteRequest:
    """Input to the Obsidian writer."""

    markdown: MarkdownArtifact
    config: ObsidianWriterConfig = field(default_factory=ObsidianWriterConfig)
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId = "obsidian"
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ObsidianNoteArtifact:
    """Artifact representing a note written into an Obsidian vault."""

    obsidian_note_artifact_id: ObsidianNoteArtifactId
    source_id: SourceId
    parent_markdown_artifact_id: str
    status: ObsidianWriteStatus
    path: Path
    uri: str
    snapshot: ArtifactSnapshot
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ObsidianWriteResult:
    """Top-level output of Obsidian writing."""

    note: ObsidianNoteArtifact | None
    status: ObsidianWriteStatus
    path: Path | None = None
    issues: tuple[ObsidianWriteIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Return whether writing succeeded."""

        return self.note is not None and not any(
            issue.severity is ObsidianWriteIssueSeverity.ERROR
            for issue in self.issues
        )


__all__ = [
    "ObsidianConflictStrategy",
    "ObsidianNoteArtifact",
    "ObsidianNoteArtifactId",
    "ObsidianWriteRequest",
    "ObsidianWriteResult",
    "ObsidianWriteStatus",
    "ObsidianWriterConfig",
]
