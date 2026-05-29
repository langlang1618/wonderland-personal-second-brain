"""Pure-rule source detector implementation."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from ai_knowledge_pipeline.core.source import MediaKind, SourceKind
from ai_knowledge_pipeline.modules.sources.errors import (
    SourceErrorCode,
    SourceIssue,
    SourceNormalizationError,
)
from ai_knowledge_pipeline.modules.sources.interfaces import SourceDetector
from ai_knowledge_pipeline.modules.sources.rules import (
    is_audio_suffix,
    is_file_url,
    is_m3u8_path,
    is_remote_url,
    is_video_suffix,
    is_youtube_host,
    local_suffix,
    normalized_host,
)
from ai_knowledge_pipeline.modules.sources.types import (
    DetectionSignal,
    RawSourceInput,
    SourceDetection,
    SourceParseContext,
)


class RuleBasedSourceDetector(SourceDetector):
    """Detect supported source families using local, deterministic rules."""

    def detect(
        self,
        raw_input: RawSourceInput,
        context: SourceParseContext,
    ) -> SourceDetection:
        candidate = raw_input.strip()
        if not candidate:
            raise SourceNormalizationError(
                SourceIssue(
                    code=SourceErrorCode.UNSUPPORTED_INPUT,
                    message="Source input is empty.",
                    field="raw_input",
                )
            )

        parsed_url = urlparse(candidate)

        if is_remote_url(parsed_url):
            return self._detect_remote(candidate, parsed_url, context)

        if is_file_url(parsed_url):
            return self._detect_local(unquote(parsed_url.path), context)

        if parsed_url.scheme and parsed_url.scheme.lower() not in {"", "file"}:
            raise SourceNormalizationError(
                SourceIssue(
                    code=SourceErrorCode.INVALID_URL,
                    message=f"Unsupported URL scheme: {parsed_url.scheme}.",
                    field="raw_input",
                    details={"scheme": parsed_url.scheme},
                )
            )

        return self._detect_local(candidate, context)

    def _detect_remote(
        self,
        raw_input: RawSourceInput,
        parsed_url,
        context: SourceParseContext,
    ) -> SourceDetection:
        if not context.config.allow_remote_sources:
            raise SourceNormalizationError(
                SourceIssue(
                    code=SourceErrorCode.REMOTE_SOURCES_DISABLED,
                    message="Remote sources are disabled by configuration.",
                    field="raw_input",
                )
            )

        host = normalized_host(parsed_url)
        if is_youtube_host(host):
            return SourceDetection(
                raw_input=raw_input,
                kind=SourceKind.YOUTUBE,
                media_kind=MediaKind.VIDEO,
                parser_name="youtube",
                confidence=0.98,
                signals=(DetectionSignal.URL_SCHEME, DetectionSignal.URL_HOST),
            )

        if is_m3u8_path(parsed_url.path):
            return SourceDetection(
                raw_input=raw_input,
                kind=SourceKind.M3U8,
                media_kind=MediaKind.VIDEO,
                parser_name="m3u8",
                confidence=0.95,
                signals=(DetectionSignal.URL_SCHEME, DetectionSignal.URL_PATH),
            )

        raise SourceNormalizationError(
            SourceIssue(
                code=SourceErrorCode.UNSUPPORTED_INPUT,
                message="Remote URL is not a supported source type.",
                field="raw_input",
                details={"host": host},
            )
        )

    def _detect_local(
        self,
        raw_input: RawSourceInput,
        context: SourceParseContext,
    ) -> SourceDetection:
        if not context.config.allow_local_sources:
            raise SourceNormalizationError(
                SourceIssue(
                    code=SourceErrorCode.LOCAL_SOURCES_DISABLED,
                    message="Local sources are disabled by configuration.",
                    field="raw_input",
                )
            )

        suffix = local_suffix(raw_input)
        if is_audio_suffix(suffix):
            return SourceDetection(
                raw_input=raw_input,
                kind=SourceKind.LOCAL_AUDIO,
                media_kind=MediaKind.AUDIO,
                parser_name="local_audio",
                confidence=0.9,
                signals=(DetectionSignal.FILE_EXTENSION,),
            )

        if is_video_suffix(suffix):
            return SourceDetection(
                raw_input=raw_input,
                kind=SourceKind.LOCAL_VIDEO,
                media_kind=MediaKind.VIDEO,
                parser_name="local_video",
                confidence=0.9,
                signals=(DetectionSignal.FILE_EXTENSION,),
            )

        raise SourceNormalizationError(
            SourceIssue(
                code=SourceErrorCode.UNSUPPORTED_MEDIA_TYPE,
                message="Local path extension is not a supported audio or video type.",
                field="raw_input",
                details={"suffix": suffix},
            )
        )


__all__ = ["RuleBasedSourceDetector"]
