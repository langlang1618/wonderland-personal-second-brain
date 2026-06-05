"""Public contracts for the transcription module."""

from ai_knowledge_pipeline.modules.transcription.errors import (
    TranscriptionErrorCode,
    TranscriptionIssue,
    TranscriptionIssueSeverity,
)
from ai_knowledge_pipeline.modules.transcription.interfaces import (
    Transcriber,
    TranscriptionProvider,
)
from ai_knowledge_pipeline.modules.transcription.local_whisper import LocalWhisperProvider
from ai_knowledge_pipeline.modules.transcription.providers import (
    UnavailableTranscriptionProvider,
)
from ai_knowledge_pipeline.modules.transcription.runtime import (
    ChunkTranscriptArtifact,
    FasterWhisperConfig,
    FasterWhisperModelSize,
    FasterWhisperProvider,
    TranscriptMergeResult,
    TranscriptMerger,
)
from ai_knowledge_pipeline.modules.transcription.transcriber import (
    DefaultTranscriber,
    create_default_transcriber,
)
from ai_knowledge_pipeline.modules.transcription.types import (
    ProviderTranscriptionResult,
    SpeakerMetadata,
    TranscriptArtifact,
    TranscriptFormat,
    TranscriptSegment,
    TranscriptTimestamp,
    TranscriptionConfig,
    TranscriptionProviderKind,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
)

__all__ = [
    "DefaultTranscriber",
    "ChunkTranscriptArtifact",
    "FasterWhisperConfig",
    "FasterWhisperModelSize",
    "FasterWhisperProvider",
    "ProviderTranscriptionResult",
    "LocalWhisperProvider",
    "SpeakerMetadata",
    "Transcriber",
    "TranscriptArtifact",
    "TranscriptFormat",
    "TranscriptMergeResult",
    "TranscriptMerger",
    "TranscriptSegment",
    "TranscriptTimestamp",
    "TranscriptionConfig",
    "TranscriptionErrorCode",
    "TranscriptionIssue",
    "TranscriptionIssueSeverity",
    "TranscriptionProvider",
    "TranscriptionProviderKind",
    "TranscriptionRequest",
    "TranscriptionResult",
    "TranscriptionStatus",
    "UnavailableTranscriptionProvider",
    "create_default_transcriber",
]
