"""Public contracts for the sources module.

Concrete source detection and normalization will be implemented in a later
step. For now this module re-exports the stable source model used by the rest
of the pipeline.
"""

from ai_knowledge_pipeline.core.source import (
    MediaKind,
    SourceAccess,
    SourceBatch,
    SourceData,
    SourceKind,
    SourceLocation,
    SourceManifestStore,
    SourceMetadata,
    SourceMetadataSchema,
    SourceModelConfig,
    SourceNormalizer,
    SourceStatus,
)
from ai_knowledge_pipeline.modules.sources.errors import (
    SourceErrorCode,
    SourceIssue,
    SourceIssueSeverity,
    SourceNormalizationError,
)
from ai_knowledge_pipeline.modules.sources.interfaces import (
    SourceDetector,
    SourceIdFactory,
    SourceManifestRepository,
    SourceManifestSerializer,
    SourceParser,
    SourcesNormalizer,
    SourceValidator,
)
from ai_knowledge_pipeline.modules.sources.normalizer import (
    DefaultSourcesNormalizer,
    create_default_sources_normalizer,
)
from ai_knowledge_pipeline.modules.sources.types import (
    DetectionSignal,
    ManifestFormat,
    RawSourceInput,
    SourceDetection,
    SourceHint,
    SourceManifestEnvelope,
    SourceManifestRef,
    SourceNormalizationResult,
    SourceParseContext,
    SourceParseRequest,
    SourceParseResult,
    SourceValidationResult,
)

__all__ = [
    "DetectionSignal",
    "DefaultSourcesNormalizer",
    "ManifestFormat",
    "MediaKind",
    "RawSourceInput",
    "SourceAccess",
    "SourceBatch",
    "SourceData",
    "SourceDetection",
    "SourceDetector",
    "SourceErrorCode",
    "SourceHint",
    "SourceIdFactory",
    "SourceIssue",
    "SourceIssueSeverity",
    "SourceKind",
    "SourceLocation",
    "SourceManifestEnvelope",
    "SourceManifestRef",
    "SourceManifestRepository",
    "SourceManifestSerializer",
    "SourceManifestStore",
    "SourceMetadata",
    "SourceMetadataSchema",
    "SourceModelConfig",
    "SourceNormalizationError",
    "SourceNormalizationResult",
    "SourceNormalizer",
    "SourceParseContext",
    "SourceParseRequest",
    "SourceParseResult",
    "SourceParser",
    "SourceStatus",
    "SourceValidationResult",
    "SourceValidator",
    "SourcesNormalizer",
    "create_default_sources_normalizer",
]
