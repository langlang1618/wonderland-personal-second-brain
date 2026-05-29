"""Public contracts for the media chunking module."""

from ai_knowledge_pipeline.modules.chunking.adapters import (
    DefaultFfmpegCommandBuilder,
    FfmpegRuntimeAdapter,
)
from ai_knowledge_pipeline.modules.chunking.chunker import (
    DefaultMediaChunker,
    create_default_media_chunker,
)
from ai_knowledge_pipeline.modules.chunking.errors import (
    MediaChunkingErrorCode,
    MediaChunkingIssue,
    MediaChunkingIssueSeverity,
)
from ai_knowledge_pipeline.modules.chunking.interfaces import (
    ChunkProcessRunner,
    FfmpegCommandBuilder,
    MediaChunker,
    MediaChunkingAdapter,
    MediaChunkPlanner,
    TimelineSegmenter,
)
from ai_knowledge_pipeline.modules.chunking.planner import (
    DefaultMediaChunkPlanner,
    FixedDurationTimelineSegmenter,
)
from ai_knowledge_pipeline.modules.chunking.runner import SubprocessFfmpegRunner
from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkArtifactId,
    ChunkCommand,
    ChunkProcessOutput,
    ChunkProcessResult,
    MediaChunkAdapterResult,
    MediaChunkArtifact,
    MediaChunkPlan,
    MediaChunkingConfig,
    MediaChunkingMode,
    MediaChunkingRequest,
    MediaChunkingResult,
    MediaChunkingStatus,
    SegmentationStrategyKind,
    TimelineSegment,
)

__all__ = [
    "ChunkArtifactId",
    "ChunkCommand",
    "ChunkProcessOutput",
    "ChunkProcessResult",
    "ChunkProcessRunner",
    "DefaultFfmpegCommandBuilder",
    "DefaultMediaChunkPlanner",
    "DefaultMediaChunker",
    "FfmpegCommandBuilder",
    "FfmpegRuntimeAdapter",
    "FixedDurationTimelineSegmenter",
    "MediaChunkAdapterResult",
    "MediaChunkArtifact",
    "MediaChunkPlan",
    "MediaChunkPlanner",
    "MediaChunker",
    "MediaChunkingAdapter",
    "MediaChunkingConfig",
    "MediaChunkingErrorCode",
    "MediaChunkingIssue",
    "MediaChunkingIssueSeverity",
    "MediaChunkingMode",
    "MediaChunkingRequest",
    "MediaChunkingResult",
    "MediaChunkingStatus",
    "SegmentationStrategyKind",
    "SubprocessFfmpegRunner",
    "TimelineSegment",
    "TimelineSegmenter",
    "create_default_media_chunker",
]
