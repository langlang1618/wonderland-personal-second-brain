"""Public contracts for the transcript cleaning module."""

from ai_knowledge_pipeline.modules.cleaning.cleaner import (
    DefaultTranscriptCleaner,
    create_default_transcript_cleaner,
)
from ai_knowledge_pipeline.modules.cleaning.errors import (
    TranscriptCleaningErrorCode,
    TranscriptCleaningIssue,
    TranscriptCleaningIssueSeverity,
)
from ai_knowledge_pipeline.modules.cleaning.interfaces import (
    TranscriptCleaner,
    TranscriptCleaningProvider,
)
from ai_knowledge_pipeline.modules.cleaning.openai_provider import OpenAICleaningProvider
from ai_knowledge_pipeline.modules.cleaning.providers import UnavailableCleaningProvider
from ai_knowledge_pipeline.modules.cleaning.types import (
    ActionItem,
    AgentMemoryCandidate,
    CleanedTranscriptArtifact,
    CleaningPromptSchema,
    CleaningProviderKind,
    CleaningProviderResult,
    KeyInsight,
    MarkdownBlockKind,
    MarkdownReadyBlock,
    MarkdownReadyChapter,
    MarkdownReadyTranscript,
    TranscriptCleaningConfig,
    TranscriptCleaningRequest,
    TranscriptCleaningResult,
    TranscriptCleaningStatus,
)

__all__ = [
    "ActionItem",
    "AgentMemoryCandidate",
    "CleanedTranscriptArtifact",
    "CleaningPromptSchema",
    "CleaningProviderKind",
    "CleaningProviderResult",
    "DefaultTranscriptCleaner",
    "KeyInsight",
    "MarkdownBlockKind",
    "MarkdownReadyBlock",
    "MarkdownReadyChapter",
    "MarkdownReadyTranscript",
    "OpenAICleaningProvider",
    "TranscriptCleaner",
    "TranscriptCleaningConfig",
    "TranscriptCleaningErrorCode",
    "TranscriptCleaningIssue",
    "TranscriptCleaningIssueSeverity",
    "TranscriptCleaningProvider",
    "TranscriptCleaningRequest",
    "TranscriptCleaningResult",
    "TranscriptCleaningStatus",
    "UnavailableCleaningProvider",
    "create_default_transcript_cleaner",
]
