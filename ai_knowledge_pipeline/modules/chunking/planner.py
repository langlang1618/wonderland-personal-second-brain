"""Timeline and path planning for media chunking."""

from __future__ import annotations

from pathlib import Path

from ai_knowledge_pipeline.modules.chunking.errors import (
    MediaChunkingErrorCode,
    MediaChunkingIssue,
)
from ai_knowledge_pipeline.modules.chunking.interfaces import (
    MediaChunkPlanner,
    TimelineSegmenter,
)
from ai_knowledge_pipeline.modules.chunking.types import (
    MediaChunkPlan,
    MediaChunkingConfig,
    MediaChunkingRequest,
    TimelineSegment,
)


class FixedDurationTimelineSegmenter(TimelineSegmenter):
    """Plan fixed-duration timeline segments."""

    def segment(
        self,
        duration_seconds: float,
        config: MediaChunkingConfig,
    ) -> tuple[TimelineSegment, ...]:
        if config.chunk_duration_seconds <= 0:
            raise ValueError("chunk_duration_seconds must be greater than zero")
        if duration_seconds <= 0:
            return ()

        segments: list[TimelineSegment] = []
        start = 0.0
        index = 0
        while start < duration_seconds:
            end = min(start + config.chunk_duration_seconds, duration_seconds)
            segments.append(
                TimelineSegment(
                    chunk_index=index,
                    start_time=start,
                    end_time=end,
                )
            )
            start = end
            index += 1
        return tuple(segments)


class DefaultMediaChunkPlanner(MediaChunkPlanner):
    """Plan chunk paths and segments without touching the filesystem."""

    def __init__(self, segmenter: TimelineSegmenter | None = None) -> None:
        self._segmenter = segmenter or FixedDurationTimelineSegmenter()

    def plan(self, request: MediaChunkingRequest) -> MediaChunkPlan:
        if request.media.path is None:
            raise MediaChunkPlanningError(
                MediaChunkingIssue(
                    code=MediaChunkingErrorCode.MISSING_MEDIA_PATH,
                    message="Media chunking requires a local media path.",
                    field="media.path",
                )
            )
        if request.media_duration_seconds is None:
            raise MediaChunkPlanningError(
                MediaChunkingIssue(
                    code=MediaChunkingErrorCode.MISSING_MEDIA_DURATION,
                    message="Media duration is required for local timeline planning.",
                    field="media_duration_seconds",
                )
            )

        try:
            segments = self._segmenter.segment(
                request.media_duration_seconds,
                request.config,
            )
        except ValueError as exc:
            raise MediaChunkPlanningError(
                MediaChunkingIssue(
                    code=MediaChunkingErrorCode.INVALID_CHUNK_DURATION,
                    message=str(exc),
                    field="config.chunk_duration_seconds",
                )
            ) from exc

        return MediaChunkPlan(
            source_id=request.media.source_id,
            parent_media_artifact_id=request.media.media_artifact_id,
            parent_snapshot_id=request.media.snapshot.snapshot_id,
            input_path=request.media.path,
            chunks_dir=request.config.chunks_dir,
            temp_dir=request.config.temp_dir,
            segments=segments,
            metadata={
                "segmentation_strategy": request.config.segmentation_strategy.value,
                "chunk_duration_seconds": request.config.chunk_duration_seconds,
            },
        )


class MediaChunkPlanningError(Exception):
    """Raised when chunk planning cannot produce a valid plan."""

    def __init__(self, issue: MediaChunkingIssue) -> None:
        super().__init__(issue.message)
        self.issue = issue


def chunk_output_path(
    chunks_dir: Path,
    source_id: str,
    chunk_index: int,
    extension: str,
) -> Path:
    """Return deterministic output path for one chunk."""

    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return chunks_dir / source_id / f"chunk_{chunk_index:04d}{normalized_extension}"


__all__ = [
    "DefaultMediaChunkPlanner",
    "FixedDurationTimelineSegmenter",
    "MediaChunkPlanningError",
    "chunk_output_path",
]
