"""Protocol boundaries for Markdown generation."""

from __future__ import annotations

from typing import Protocol

from ai_knowledge_pipeline.modules.markdown.types import (
    MarkdownGenerationRequest,
    MarkdownGenerationResult,
    MarkdownRenderResult,
)


class MarkdownRenderer(Protocol):
    """Render cleaned transcript content into Markdown text."""

    def render(self, request: MarkdownGenerationRequest) -> MarkdownRenderResult:
        """Return Markdown text and frontmatter."""


class MarkdownGenerator(Protocol):
    """Top-level Markdown generation boundary."""

    def generate(self, request: MarkdownGenerationRequest) -> MarkdownGenerationResult:
        """Convert a CleanedTranscriptArtifact into a MarkdownArtifact."""


__all__ = ["MarkdownGenerator", "MarkdownRenderer"]
