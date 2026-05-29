"""Sources normalizer implementation."""

from __future__ import annotations

from ai_knowledge_pipeline.modules.sources.detector import RuleBasedSourceDetector
from ai_knowledge_pipeline.modules.sources.errors import SourceNormalizationError
from ai_knowledge_pipeline.modules.sources.id_factory import StableSourceIdFactory
from ai_knowledge_pipeline.modules.sources.interfaces import SourceDetector, SourcesNormalizer
from ai_knowledge_pipeline.modules.sources.parsers import (
    ParserRegistry,
    default_parser_registry,
    parser_not_found_result,
)
from ai_knowledge_pipeline.modules.sources.types import (
    RawSourceInput,
    SourceNormalizationResult,
    SourceParseContext,
    SourceParseRequest,
)


class DefaultSourcesNormalizer(SourcesNormalizer):
    """Default detector + parser orchestration."""

    def __init__(
        self,
        detector: SourceDetector,
        parser_registry: ParserRegistry,
    ) -> None:
        self._detector = detector
        self._parser_registry = parser_registry

    def normalize(
        self,
        raw_input: RawSourceInput,
        context: SourceParseContext,
    ) -> SourceNormalizationResult:
        try:
            detection = self._detector.detect(raw_input, context)
        except SourceNormalizationError as exc:
            return SourceNormalizationResult(
                source=None,
                issues=(exc.issue,),
            )

        request = SourceParseRequest(
            raw_input=raw_input,
            detection=detection,
            context=context,
        )
        parser = self._parser_registry.get(detection.parser_name)
        parse_result = (
            parser.parse(request) if parser is not None else parser_not_found_result(request)
        )

        return SourceNormalizationResult(
            source=parse_result.source,
            detection=detection,
            issues=(*detection.issues, *parse_result.issues),
        )


def create_default_sources_normalizer() -> DefaultSourcesNormalizer:
    """Create the default pure-rule sources normalizer."""

    id_factory = StableSourceIdFactory()
    return DefaultSourcesNormalizer(
        detector=RuleBasedSourceDetector(),
        parser_registry=default_parser_registry(id_factory),
    )


__all__ = ["DefaultSourcesNormalizer", "create_default_sources_normalizer"]
