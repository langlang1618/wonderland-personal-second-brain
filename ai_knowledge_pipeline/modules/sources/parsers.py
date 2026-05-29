"""Source parser implementations.

Parsers turn a detection result into SourceData. They do not download media,
probe files, call external tools, or access the network.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from ai_knowledge_pipeline.core.source import (
    SourceAccess,
    SourceData,
    SourceLocation,
    SourceMetadata,
)
from ai_knowledge_pipeline.modules.sources.errors import (
    SourceErrorCode,
    SourceIssue,
)
from ai_knowledge_pipeline.modules.sources.interfaces import SourceIdFactory, SourceParser
from ai_knowledge_pipeline.modules.sources.types import (
    SourceParseRequest,
    SourceParseResult,
)


class BaseSourceParser(SourceParser):
    """Shared parser helpers."""

    name: str

    def __init__(self, id_factory: SourceIdFactory) -> None:
        self._id_factory = id_factory

    def _source_id(self, request: SourceParseRequest) -> str:
        return self._id_factory.create_id(request.raw_input, request.detection)

    def _tags(self, request: SourceParseRequest) -> tuple[str, ...]:
        default_tags = request.context.config.default_tags
        hint_tags = request.context.hint.tags if request.context.hint else ()
        return tuple(dict.fromkeys((*default_tags, *hint_tags)))

    def _title(self, request: SourceParseRequest) -> str | None:
        return request.context.hint.title if request.context.hint else None


class YouTubeSourceParser(BaseSourceParser):
    """Parse a detected YouTube URL into SourceData."""

    name = "youtube"

    def parse(self, request: SourceParseRequest) -> SourceParseResult:
        source = SourceData(
            source_id=self._source_id(request),
            kind=request.detection.kind,
            media_kind=request.detection.media_kind,
            location=SourceLocation(
                access=SourceAccess.REMOTE,
                uri=request.raw_input.strip(),
            ),
            metadata=SourceMetadata(
                title=self._title(request),
                language=request.context.config.default_language,
                source_url=request.raw_input.strip(),
                canonical_url=request.raw_input.strip(),
                origin_platform="youtube",
                tags=self._tags(request),
                extra=request.context.hint.metadata if request.context.hint else {},
            ),
            preferred_track="audio" if request.context.config.prefer_audio else "video",
            config_profile=request.context.config_profile,
        )
        return SourceParseResult(source=source)


class M3U8SourceParser(BaseSourceParser):
    """Parse a detected m3u8 URL into SourceData."""

    name = "m3u8"

    def parse(self, request: SourceParseRequest) -> SourceParseResult:
        source = SourceData(
            source_id=self._source_id(request),
            kind=request.detection.kind,
            media_kind=request.detection.media_kind,
            location=SourceLocation(
                access=SourceAccess.REMOTE,
                uri=request.raw_input.strip(),
            ),
            metadata=SourceMetadata(
                title=self._title(request),
                language=request.context.config.default_language,
                source_url=request.raw_input.strip(),
                canonical_url=request.raw_input.strip(),
                origin_platform="m3u8",
                tags=self._tags(request),
                extra=request.context.hint.metadata if request.context.hint else {},
            ),
            preferred_track="audio" if request.context.config.prefer_audio else "video",
            config_profile=request.context.config_profile,
        )
        return SourceParseResult(source=source)


class LocalSourceParser(BaseSourceParser):
    """Parse a detected local path into SourceData."""

    def parse(self, request: SourceParseRequest) -> SourceParseResult:
        raw_input = request.raw_input.strip()
        parsed = urlparse(raw_input)
        path_text = unquote(parsed.path) if parsed.scheme == "file" else raw_input
        path = Path(path_text)

        source = SourceData(
            source_id=self._source_id(request),
            kind=request.detection.kind,
            media_kind=request.detection.media_kind,
            location=SourceLocation(
                access=SourceAccess.LOCAL,
                uri=raw_input,
                path=path,
            ),
            metadata=SourceMetadata(
                title=self._title(request),
                language=request.context.config.default_language,
                local_path=path,
                origin_platform="local",
                tags=self._tags(request),
                extra=request.context.hint.metadata if request.context.hint else {},
            ),
            preferred_track="audio" if request.context.config.prefer_audio else "video",
            config_profile=request.context.config_profile,
        )
        return SourceParseResult(source=source)


class LocalAudioSourceParser(LocalSourceParser):
    """Parse a detected local audio path into SourceData."""

    name = "local_audio"


class LocalVideoSourceParser(LocalSourceParser):
    """Parse a detected local video path into SourceData."""

    name = "local_video"


class ParserRegistry:
    """Small parser registry used by the normalizer."""

    def __init__(self, parsers: tuple[SourceParser, ...]) -> None:
        self._parsers = {parser.name: parser for parser in parsers}

    def get(self, name: str) -> SourceParser | None:
        return self._parsers.get(name)


def default_parser_registry(id_factory: SourceIdFactory) -> ParserRegistry:
    """Return the default parser registry."""

    return ParserRegistry(
        parsers=(
            YouTubeSourceParser(id_factory),
            M3U8SourceParser(id_factory),
            LocalAudioSourceParser(id_factory),
            LocalVideoSourceParser(id_factory),
        )
    )


def parser_not_found_result(request: SourceParseRequest) -> SourceParseResult:
    """Return a structured parser-not-found result."""

    return SourceParseResult(
        source=None,
        issues=(
            SourceIssue(
                code=SourceErrorCode.UNSUPPORTED_INPUT,
                message="No parser is registered for detected source.",
                field="parser_name",
                details={"parser_name": request.detection.parser_name},
            ),
        ),
    )


__all__ = [
    "BaseSourceParser",
    "LocalAudioSourceParser",
    "LocalSourceParser",
    "LocalVideoSourceParser",
    "M3U8SourceParser",
    "ParserRegistry",
    "YouTubeSourceParser",
    "default_parser_registry",
    "parser_not_found_result",
]
