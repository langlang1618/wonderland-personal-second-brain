"""Typed contracts for Markdown generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypeAlias

from ai_knowledge_pipeline.core.artifact import ArtifactSnapshot
from ai_knowledge_pipeline.core.runtime import JobId, RunId, StageId, TaskId
from ai_knowledge_pipeline.core.source import MetadataMap, SourceId
from ai_knowledge_pipeline.modules.cleaning.types import CleanedTranscriptArtifact
from ai_knowledge_pipeline.modules.markdown.errors import (
    MarkdownGenerationIssue,
    MarkdownGenerationIssueSeverity,
)


MarkdownArtifactId: TypeAlias = str
YamlScalar: TypeAlias = str | int | float | bool | None
YamlFrontmatter: TypeAlias = Mapping[str, YamlScalar | tuple[YamlScalar, ...]]


class MarkdownGenerationStatus(StrEnum):
    """Lifecycle status for Markdown outputs."""

    GENERATED = "generated"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class MarkdownGenerationConfig:
    """Configuration knobs for Markdown generation."""

    markdown_dir: Path = Path("data/markdown")
    include_frontmatter: bool = True
    include_summary: bool = True
    include_key_insights: bool = True
    include_action_items: bool = True
    include_tags_section: bool = True
    file_extension: str = ".md"


@dataclass(frozen=True, slots=True)
class MarkdownGenerationRequest:
    """Input to the Markdown generation layer."""

    cleaned_transcript: CleanedTranscriptArtifact
    config: MarkdownGenerationConfig = field(default_factory=MarkdownGenerationConfig)
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId = "markdown"
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MarkdownRenderResult:
    """Rendered Markdown text and frontmatter."""

    markdown_text: str
    frontmatter: YamlFrontmatter = field(default_factory=dict)
    issues: tuple[MarkdownGenerationIssue, ...] = ()

    @property
    def is_success(self) -> bool:
        """Return whether render output has no error-severity issues."""

        return bool(self.markdown_text) and not any(
            issue.severity is MarkdownGenerationIssueSeverity.ERROR
            for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class MarkdownArtifact:
    """Unified Markdown artifact emitted by Markdown generation."""

    markdown_artifact_id: MarkdownArtifactId
    source_id: SourceId
    parent_cleaned_transcript_artifact_id: str
    chunk_index: int
    status: MarkdownGenerationStatus
    markdown_text: str
    frontmatter: YamlFrontmatter
    path: Path | None
    uri: str
    snapshot: ArtifactSnapshot
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MarkdownGenerationResult:
    """Top-level output of Markdown generation."""

    markdown: MarkdownArtifact | None
    status: MarkdownGenerationStatus
    issues: tuple[MarkdownGenerationIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Return whether Markdown generation produced an artifact."""

        return self.markdown is not None and not any(
            issue.severity is MarkdownGenerationIssueSeverity.ERROR
            for issue in self.issues
        )


__all__ = [
    "MarkdownArtifact",
    "MarkdownArtifactId",
    "MarkdownGenerationConfig",
    "MarkdownGenerationRequest",
    "MarkdownGenerationResult",
    "MarkdownGenerationStatus",
    "MarkdownRenderResult",
    "YamlFrontmatter",
    "YamlScalar",
]
