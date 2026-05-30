"""Typed contracts for the transcript cleaning layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypeAlias

from ai_knowledge_pipeline.core.artifact import ArtifactSnapshot
from ai_knowledge_pipeline.core.runtime import JobId, RunId, StageId, TaskId
from ai_knowledge_pipeline.core.source import MetadataMap, SourceId
from ai_knowledge_pipeline.modules.cleaning.errors import (
    TranscriptCleaningIssue,
    TranscriptCleaningIssueSeverity,
)
from ai_knowledge_pipeline.modules.transcription.types import TranscriptArtifact


CleanedTranscriptArtifactId: TypeAlias = str


class CleaningProviderKind(StrEnum):
    """Supported future cleaning provider families."""

    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    GEMINI = "gemini"
    LOCAL_LLM = "local_llm"
    MOCK = "mock"


class TranscriptCleaningStatus(StrEnum):
    """Lifecycle status for cleaned transcript outputs."""

    CLEANED = "cleaned"
    FAILED = "failed"
    SKIPPED = "skipped"


class MarkdownBlockKind(StrEnum):
    """Markdown-ready block families."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    QUOTE = "quote"
    CODE = "code"


@dataclass(frozen=True, slots=True)
class CleaningPromptSchema:
    """Provider-agnostic prompt schema for transcript cleaning."""

    system_instruction: str
    task_instruction: str
    terminology: tuple[str, ...] = ()
    output_requirements: tuple[str, ...] = ()
    style_guide: str | None = None
    prompt_version: str = "cleaning-v1"


@dataclass(frozen=True, slots=True)
class MarkdownReadyBlock:
    """One structured block ready for Markdown rendering."""

    block_index: int
    kind: MarkdownBlockKind
    text: str
    heading_level: int | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MarkdownReadyChapter:
    """One cleaned transcript chapter."""

    chapter_index: int
    title: str
    summary: str | None = None
    blocks: tuple[MarkdownReadyBlock, ...] = ()
    start_time: float | None = None
    end_time: float | None = None
    semantic_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KeyInsight:
    """One extracted key insight."""

    insight_index: int
    text: str
    confidence: float | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionItem:
    """One extracted action item."""

    action_index: int
    text: str
    owner: str | None = None
    due: str | None = None


@dataclass(frozen=True, slots=True)
class AgentMemoryCandidate:
    """Future-compatible agent memory extraction candidate."""

    memory_index: int
    text: str
    memory_type: str | None = None
    importance: float | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarkdownReadyTranscript:
    """Structured cleaned content ready for downstream Markdown/RAG."""

    title: str
    summary: str
    cleaned_text: str
    chapters: tuple[MarkdownReadyChapter, ...] = ()
    key_insights: tuple[KeyInsight, ...] = ()
    action_items: tuple[ActionItem, ...] = ()
    semantic_tags: tuple[str, ...] = ()
    agent_memory_candidates: tuple[AgentMemoryCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class TranscriptCleaningConfig:
    """Configuration knobs for transcript cleaning."""

    cleaned_transcripts_dir: Path = Path("data/transcripts/cleaned")
    provider: CleaningProviderKind = CleaningProviderKind.MOCK
    model_name: str | None = None
    prompt_version: str = "cleaning-v1"
    language: str | None = None
    env_path: Path = Path(".env")
    api_key_env_var: str = "OPENAI_API_KEY"


@dataclass(frozen=True, slots=True)
class TranscriptCleaningRequest:
    """Input to the transcript cleaning layer."""

    transcript: TranscriptArtifact
    prompt: CleaningPromptSchema
    config: TranscriptCleaningConfig = field(default_factory=TranscriptCleaningConfig)
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId = "cleaning"
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CleaningProviderResult:
    """Provider output before artifact materialization."""

    markdown_ready: MarkdownReadyTranscript | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    language: str | None = None
    confidence: float | None = None
    metadata: MetadataMap = field(default_factory=dict)
    issues: tuple[TranscriptCleaningIssue, ...] = ()

    @property
    def is_success(self) -> bool:
        """Return whether provider output is usable."""

        return self.markdown_ready is not None and not any(
            issue.severity is TranscriptCleaningIssueSeverity.ERROR
            for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class CleanedTranscriptArtifact:
    """Unified cleaned transcript artifact emitted by cleaning."""

    cleaned_transcript_artifact_id: CleanedTranscriptArtifactId
    source_id: SourceId
    parent_transcript_artifact_id: str
    chunk_index: int
    status: TranscriptCleaningStatus
    markdown_ready: MarkdownReadyTranscript
    language: str | None
    confidence: float | None
    path: Path | None
    uri: str
    snapshot: ArtifactSnapshot
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranscriptCleaningResult:
    """Top-level output of transcript cleaning."""

    cleaned_transcript: CleanedTranscriptArtifact | None
    status: TranscriptCleaningStatus
    issues: tuple[TranscriptCleaningIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Return whether cleaning produced an artifact."""

        return self.cleaned_transcript is not None and not any(
            issue.severity is TranscriptCleaningIssueSeverity.ERROR
            for issue in self.issues
        )


__all__ = [
    "ActionItem",
    "AgentMemoryCandidate",
    "CleanedTranscriptArtifact",
    "CleanedTranscriptArtifactId",
    "CleaningPromptSchema",
    "CleaningProviderKind",
    "CleaningProviderResult",
    "KeyInsight",
    "MarkdownBlockKind",
    "MarkdownReadyBlock",
    "MarkdownReadyChapter",
    "MarkdownReadyTranscript",
    "TranscriptCleaningConfig",
    "TranscriptCleaningRequest",
    "TranscriptCleaningResult",
    "TranscriptCleaningStatus",
]
