"""Public contracts for the transcript cleaning module."""

from ai_knowledge_pipeline.modules.cleaning.cleaner import (
    DefaultTranscriptCleaner,
    create_default_transcript_cleaner,
)
from ai_knowledge_pipeline.modules.cleaning.deepseek_provider import DeepSeekCleaningProvider
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
from ai_knowledge_pipeline.modules.cleaning.profiles import (
    KnowledgeProfile,
    KnowledgeProfileLoader,
    KnowledgeProfileName,
    compose_cleaning_prompt,
    load_knowledge_profile,
)
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
    "DeepSeekCleaningProvider",
    "DefaultTranscriptCleaner",
    "KeyInsight",
    "KnowledgeProfile",
    "KnowledgeProfileLoader",
    "KnowledgeProfileName",
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
    "compose_cleaning_prompt",
    "create_default_transcript_cleaner",
    "load_knowledge_profile",
]
