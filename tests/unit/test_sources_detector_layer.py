from pathlib import Path

from ai_knowledge_pipeline.core.source import (
    MediaKind,
    SourceAccess,
    SourceKind,
    SourceModelConfig,
)
from ai_knowledge_pipeline.modules.sources.contracts import (
    SourceErrorCode,
    SourceHint,
    SourceParseContext,
    create_default_sources_normalizer,
)


def normalize(raw_input: str, config: SourceModelConfig | None = None):
    normalizer = create_default_sources_normalizer()
    context = SourceParseContext(config=config or SourceModelConfig())
    return normalizer.normalize(raw_input, context)


def test_detects_and_parses_youtube_url() -> None:
    result = normalize("https://www.youtube.com/watch?v=abc123")

    assert result.is_success
    assert result.source is not None
    assert result.source.kind is SourceKind.YOUTUBE
    assert result.source.media_kind is MediaKind.VIDEO
    assert result.source.location.access is SourceAccess.REMOTE
    assert result.source.metadata.origin_platform == "youtube"
    assert result.detection is not None
    assert result.detection.parser_name == "youtube"


def test_detects_and_parses_short_youtube_url() -> None:
    result = normalize("https://youtu.be/abc123")

    assert result.is_success
    assert result.source is not None
    assert result.source.kind is SourceKind.YOUTUBE


def test_detects_and_parses_m3u8_url() -> None:
    result = normalize("https://cdn.example.com/course/playlist.m3u8?token=abc")

    assert result.is_success
    assert result.source is not None
    assert result.source.kind is SourceKind.M3U8
    assert result.source.media_kind is MediaKind.VIDEO
    assert result.source.metadata.origin_platform == "m3u8"


def test_detects_and_parses_local_video_path_without_file_io() -> None:
    result = normalize("/tmp/does-not-need-to-exist/lecture.MP4")

    assert result.is_success
    assert result.source is not None
    assert result.source.kind is SourceKind.LOCAL_VIDEO
    assert result.source.location.access is SourceAccess.LOCAL
    assert result.source.location.path == Path("/tmp/does-not-need-to-exist/lecture.MP4")


def test_detects_and_parses_local_audio_path_without_file_io() -> None:
    result = normalize("audio/session.flac")

    assert result.is_success
    assert result.source is not None
    assert result.source.kind is SourceKind.LOCAL_AUDIO
    assert result.source.media_kind is MediaKind.AUDIO


def test_detects_and_parses_file_url_as_local_audio() -> None:
    result = normalize("file:///Users/example/audio.mp3")

    assert result.is_success
    assert result.source is not None
    assert result.source.kind is SourceKind.LOCAL_AUDIO
    assert result.source.location.path == Path("/Users/example/audio.mp3")


def test_rejects_unsupported_remote_url() -> None:
    result = normalize("https://example.com/index.html")

    assert not result.is_success
    assert result.issues[0].code is SourceErrorCode.UNSUPPORTED_INPUT


def test_rejects_unsupported_local_extension() -> None:
    result = normalize("notes/course.txt")

    assert not result.is_success
    assert result.issues[0].code is SourceErrorCode.UNSUPPORTED_MEDIA_TYPE


def test_respects_remote_source_config() -> None:
    result = normalize(
        "https://www.youtube.com/watch?v=abc123",
        config=SourceModelConfig(allow_remote_sources=False),
    )

    assert not result.is_success
    assert result.issues[0].code is SourceErrorCode.REMOTE_SOURCES_DISABLED


def test_respects_local_source_config() -> None:
    result = normalize(
        "audio/session.mp3",
        config=SourceModelConfig(allow_local_sources=False),
    )

    assert not result.is_success
    assert result.issues[0].code is SourceErrorCode.LOCAL_SOURCES_DISABLED


def test_parser_applies_config_and_hints() -> None:
    normalizer = create_default_sources_normalizer()
    context = SourceParseContext(
        config=SourceModelConfig(
            default_language="zh",
            default_tags=("course",),
            prefer_audio=False,
        ),
        config_profile="dev",
        hint=SourceHint(title="Lecture 01", tags=("ai",), metadata={"level": "intro"}),
    )

    result = normalizer.normalize("video/lecture.mov", context)

    assert result.is_success
    assert result.source is not None
    assert result.source.metadata.title == "Lecture 01"
    assert result.source.metadata.language == "zh"
    assert result.source.metadata.tags == ("course", "ai")
    assert result.source.metadata.extra == {"level": "intro"}
    assert result.source.preferred_track == "video"
    assert result.source.config_profile == "dev"


def test_source_id_is_stable_for_same_input() -> None:
    first = normalize("audio/session.wav")
    second = normalize("audio/session.wav")

    assert first.source is not None
    assert second.source is not None
    assert first.source.source_id == second.source.source_id
