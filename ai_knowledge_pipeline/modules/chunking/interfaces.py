"""Protocol boundaries for the media chunking layer."""

from __future__ import annotations

from typing import Protocol

from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkCommand,
    ChunkProcessResult,
    MediaChunkAdapterResult,
    MediaChunkPlan,
    MediaChunkingConfig,
    MediaChunkingRequest,
    MediaChunkingResult,
    TimelineSegment,
)


class TimelineSegmenter(Protocol):
    """Plan media timeline segments."""

    def segment(
        self,
        duration_seconds: float,
        config: MediaChunkingConfig,
    ) -> tuple[TimelineSegment, ...]:
        """Return timeline segments for a media duration."""


class MediaChunkPlanner(Protocol):
    """Plan chunk output paths and timeline segments."""

    def plan(self, request: MediaChunkingRequest) -> MediaChunkPlan:
        """Return a pure chunking plan without touching the filesystem."""


class FfmpegCommandBuilder(Protocol):
    """Build ffmpeg command arguments without executing them."""

    def build(
        self,
        request: MediaChunkingRequest,
        plan: MediaChunkPlan,
    ) -> tuple[ChunkCommand, ...]:
        """Return one ffmpeg command per planned chunk."""


class ChunkProcessRunner(Protocol):
    """Execute prepared ffmpeg commands."""

    def run(
        self,
        command: ChunkCommand,
        config: MediaChunkingConfig,
    ) -> ChunkProcessResult:
        """Run one command and return structured subprocess output."""


class MediaChunkingAdapter(Protocol):
    """Boundary for concrete media chunking adapters."""

    name: str

    def chunk(
        self,
        request: MediaChunkingRequest,
        plan: MediaChunkPlan,
    ) -> MediaChunkAdapterResult:
        """Materialize media chunks according to a plan."""


class MediaChunker(Protocol):
    """Top-level media chunking boundary."""

    def chunk(self, request: MediaChunkingRequest) -> MediaChunkingResult:
        """Convert LocalMediaArtifact into MediaChunk artifacts."""


__all__ = [
    "ChunkProcessRunner",
    "FfmpegCommandBuilder",
    "MediaChunker",
    "MediaChunkingAdapter",
    "MediaChunkPlanner",
    "TimelineSegmenter",
]
