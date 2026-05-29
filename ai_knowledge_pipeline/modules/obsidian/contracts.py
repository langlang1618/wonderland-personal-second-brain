"""Public contracts for the Obsidian writer module."""

from ai_knowledge_pipeline.modules.obsidian.errors import (
    ObsidianWriteErrorCode,
    ObsidianWriteIssue,
    ObsidianWriteIssueSeverity,
)
from ai_knowledge_pipeline.modules.obsidian.interfaces import (
    ObsidianPathPlanner,
    ObsidianWriter,
)
from ai_knowledge_pipeline.modules.obsidian.planner import DefaultObsidianPathPlanner
from ai_knowledge_pipeline.modules.obsidian.types import (
    ObsidianConflictStrategy,
    ObsidianNoteArtifact,
    ObsidianNoteArtifactId,
    ObsidianWriteRequest,
    ObsidianWriteResult,
    ObsidianWriteStatus,
    ObsidianWriterConfig,
)
from ai_knowledge_pipeline.modules.obsidian.writer import (
    DefaultObsidianWriter,
    create_default_obsidian_writer,
)

__all__ = [
    "DefaultObsidianPathPlanner",
    "DefaultObsidianWriter",
    "ObsidianConflictStrategy",
    "ObsidianNoteArtifact",
    "ObsidianNoteArtifactId",
    "ObsidianPathPlanner",
    "ObsidianWriteErrorCode",
    "ObsidianWriteIssue",
    "ObsidianWriteIssueSeverity",
    "ObsidianWriteRequest",
    "ObsidianWriteResult",
    "ObsidianWriteStatus",
    "ObsidianWriter",
    "ObsidianWriterConfig",
    "create_default_obsidian_writer",
]
