"""Protocol boundaries for Obsidian writing."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ai_knowledge_pipeline.modules.obsidian.types import (
    ObsidianWriteRequest,
    ObsidianWriteResult,
)


class ObsidianPathPlanner(Protocol):
    """Plan note paths inside a vault."""

    def plan_path(self, request: ObsidianWriteRequest) -> Path:
        """Return target note path."""


class ObsidianWriter(Protocol):
    """Top-level Obsidian writer boundary."""

    def write(self, request: ObsidianWriteRequest) -> ObsidianWriteResult:
        """Write a MarkdownArtifact into an Obsidian vault."""


__all__ = ["ObsidianPathPlanner", "ObsidianWriter"]
