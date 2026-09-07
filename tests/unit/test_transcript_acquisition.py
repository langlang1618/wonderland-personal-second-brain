import json
from dataclasses import replace
from pathlib import Path

import pytest

from ai_knowledge_pipeline.core.source import (
    MediaKind,
    SourceAccess,
    SourceData,
    SourceKind,
    SourceLocation,
    SourceMetadata,
)
from ai_knowledge_pipeline.modules.transcription.acquisition import (
    TranscriptAcquisitionCoordinator,
    TranscriptAcquisitionError,
    TranscriptAcquisitionGoal,
    TranscriptAcquisitionMethod,
    TranscriptAcquisitionPolicy,
    TranscriptAcquisitionRequest,
    WhisperFallbackResult,
)
from ai_knowledge_pipeline.modules.transcription.runtime.youtube_subtitles import (
    YouTubeSubtitleInspectionResult,
    YouTubeSubtitleKind,
    YouTubeSubtitleResult,
    YouTubeSubtitleStatus,
)


ENGLISH_TEXT = "Create a reusable transcript from this technical English lesson."


def _source(url: str = "https://www.youtube.com/watch?v=course") -> SourceData:
    return SourceData(
        source_id="youtube_course",
        kind=SourceKind.YOUTUBE,
        media_kind=MediaKind.VIDEO,
        location=SourceLocation(access=SourceAccess.REMOTE, uri=url),
        metadata=SourceMetadata(title="Course", language="en"),
    )


def _request(tmp_path: Path, *, skip_existing: bool = False) -> TranscriptAcquisitionRequest:
    return TranscriptAcquisitionRequest(
        source=_source(),
        output_dir=tmp_path,
        policy=TranscriptAcquisitionPolicy(
            goal=TranscriptAcquisitionGoal.ENGLISH_LEARNING,
            subtitle_language_preferences=("en", "en-US", "en-GB"),
            whisper_language="en",
            expected_language="en",
        ),
        skip_existing=skip_existing,
    )


def _inspection(
    *,
    manual: tuple[str, ...] = (),
    automatic: tuple[str, ...] = (),
) -> YouTubeSubtitleInspectionResult:
    return YouTubeSubtitleInspectionResult(
        status=YouTubeSubtitleStatus.AVAILABLE,
        manual_languages=manual,
        automatic_languages=automatic,
        executable="/runtime/yt-dlp",
        version="2026.08.19",
    )


def _successful_extractor(calls: list[YouTubeSubtitleRequest], text: str = ENGLISH_TEXT):
    def extract(request: YouTubeSubtitleRequest) -> YouTubeSubtitleResult:
        calls.append(request)
        request.output_dir.mkdir(parents=True, exist_ok=True)
        path = request.output_dir / "merged_transcript.txt"
        path.write_text(text, encoding="utf-8")
        return YouTubeSubtitleResult(
            status=YouTubeSubtitleStatus.AVAILABLE,
            transcript_path=path,
        )

    return extract


def _unexpected_whisper(language: str | None) -> WhisperFallbackResult:
    raise AssertionError("Whisper fallback must not run")


def test_manual_english_subtitle_has_priority(tmp_path) -> None:
    calls: list[YouTubeSubtitleRequest] = []
    coordinator = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: _inspection(
            manual=("en",), automatic=("en",)
        ),
        subtitle_extractor=_successful_extractor(calls),
    )

    result = coordinator.acquire(_request(tmp_path), whisper_fallback=_unexpected_whisper)

    assert result.method is TranscriptAcquisitionMethod.YOUTUBE_MANUAL_SUBTITLE
    assert result.transcript.text == ENGLISH_TEXT
    assert calls[0].subtitle_kind is YouTubeSubtitleKind.MANUAL
    assert calls[0].language == "en"


def test_automatic_english_is_selected_when_manual_is_absent(tmp_path) -> None:
    calls: list[YouTubeSubtitleRequest] = []
    coordinator = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: _inspection(automatic=("en-US",)),
        subtitle_extractor=_successful_extractor(calls),
    )

    result = coordinator.acquire(_request(tmp_path), whisper_fallback=_unexpected_whisper)

    assert result.method is TranscriptAcquisitionMethod.YOUTUBE_AUTOMATIC_CAPTION
    assert calls[0].subtitle_kind is YouTubeSubtitleKind.AUTOMATIC
    assert calls[0].language == "en-US"


@pytest.mark.parametrize(
    "inspection",
    [
        _inspection(manual=("zh-Hans",), automatic=("zh",)),
        YouTubeSubtitleInspectionResult(
            status=YouTubeSubtitleStatus.FAILED,
            message="inspection unavailable",
        ),
    ],
)
def test_no_usable_english_or_inspection_failure_falls_back_to_english_whisper(
    tmp_path,
    inspection,
) -> None:
    received_languages: list[str | None] = []

    def whisper(language: str | None) -> WhisperFallbackResult:
        received_languages.append(language)
        path = tmp_path / "merged_transcript.txt"
        path.write_text(ENGLISH_TEXT, encoding="utf-8")
        return WhisperFallbackResult(path)

    coordinator = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: inspection,
        subtitle_extractor=lambda request: pytest.fail("subtitle download must not run"),
    )

    result = coordinator.acquire(_request(tmp_path), whisper_fallback=whisper)

    assert result.method is TranscriptAcquisitionMethod.WHISPER
    assert received_languages == ["en"]


@pytest.mark.parametrize(
    "subtitle_result",
    [
        YouTubeSubtitleResult(
            status=YouTubeSubtitleStatus.FAILED,
            message="download failed",
        ),
        YouTubeSubtitleResult(status=YouTubeSubtitleStatus.UNAVAILABLE),
    ],
)
def test_subtitle_download_failure_or_empty_output_falls_back(
    tmp_path,
    subtitle_result,
) -> None:
    def whisper(language: str | None) -> WhisperFallbackResult:
        path = tmp_path / "merged_transcript.txt"
        path.write_text(ENGLISH_TEXT, encoding="utf-8")
        return WhisperFallbackResult(path)

    coordinator = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: _inspection(manual=("en",)),
        subtitle_extractor=lambda request: subtitle_result,
    )

    result = coordinator.acquire(_request(tmp_path), whisper_fallback=whisper)

    assert result.method is TranscriptAcquisitionMethod.WHISPER


def test_empty_subtitle_file_falls_back_to_whisper(tmp_path) -> None:
    def extract(request: YouTubeSubtitleRequest) -> YouTubeSubtitleResult:
        path = tmp_path / "merged_transcript.txt"
        path.write_text("", encoding="utf-8")
        return YouTubeSubtitleResult(
            status=YouTubeSubtitleStatus.AVAILABLE,
            transcript_path=path,
        )

    def whisper(language: str | None) -> WhisperFallbackResult:
        path = tmp_path / "merged_transcript.txt"
        path.write_text(ENGLISH_TEXT, encoding="utf-8")
        return WhisperFallbackResult(path)

    result = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: _inspection(manual=("en",)),
        subtitle_extractor=extract,
    ).acquire(_request(tmp_path), whisper_fallback=whisper)

    assert result.method is TranscriptAcquisitionMethod.WHISPER
    assert any("transcript is empty" in warning for warning in result.warnings)


def test_cjk_dominant_subtitle_is_rejected_and_whisper_is_used(tmp_path) -> None:
    calls: list[YouTubeSubtitleRequest] = []

    def whisper(language: str | None) -> WhisperFallbackResult:
        path = tmp_path / "merged_transcript.txt"
        path.write_text(ENGLISH_TEXT, encoding="utf-8")
        return WhisperFallbackResult(path)

    coordinator = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: _inspection(manual=("en",)),
        subtitle_extractor=_successful_extractor(
            calls,
            "这是一段明显以中文为主的错误字幕内容，不应该用于英语听力学习。",
        ),
    )

    result = coordinator.acquire(_request(tmp_path), whisper_fallback=whisper)

    assert result.method is TranscriptAcquisitionMethod.WHISPER
    assert any("CJK-dominant" in warning for warning in result.warnings)


def test_invalid_whisper_output_fails_clearly(tmp_path) -> None:
    def whisper(language: str | None) -> WhisperFallbackResult:
        path = tmp_path / "merged_transcript.txt"
        path.write_text("short", encoding="utf-8")
        return WhisperFallbackResult(path)

    coordinator = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: _inspection(),
        subtitle_extractor=lambda request: pytest.fail("subtitle download must not run"),
    )

    with pytest.raises(TranscriptAcquisitionError, match="failed validation"):
        coordinator.acquire(_request(tmp_path), whisper_fallback=whisper)


def test_non_youtube_source_uses_whisper_without_subtitle_inspection(tmp_path) -> None:
    request = _request(tmp_path)
    media_source = replace(
        request.source,
        kind=SourceKind.M3U8,
        location=SourceLocation(
            access=SourceAccess.REMOTE,
            uri="https://example.test/course.m3u8",
        ),
    )

    def whisper(language: str | None) -> WhisperFallbackResult:
        path = tmp_path / "merged_transcript.txt"
        path.write_text(ENGLISH_TEXT, encoding="utf-8")
        return WhisperFallbackResult(path)

    result = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: pytest.fail("inspection must not run"),
        subtitle_extractor=lambda request: pytest.fail("download must not run"),
    ).acquire(
        replace(request, source=media_source),
        whisper_fallback=whisper,
    )

    assert result.method is TranscriptAcquisitionMethod.WHISPER


def test_compatible_cache_is_reused_without_inspection_or_whisper(tmp_path) -> None:
    calls: list[str] = []
    first = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: _inspection(manual=("en",)),
        subtitle_extractor=_successful_extractor([]),
    )
    first.acquire(_request(tmp_path), whisper_fallback=_unexpected_whisper)

    cached = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: calls.append("inspect"),
        subtitle_extractor=lambda request: pytest.fail("download must not run"),
    ).acquire(_request(tmp_path, skip_existing=True), whisper_fallback=_unexpected_whisper)

    assert cached.method is TranscriptAcquisitionMethod.CACHED
    assert calls == []


def test_incompatible_zh_cache_is_not_reused_for_english(tmp_path) -> None:
    transcript_path = tmp_path / "merged_transcript.txt"
    transcript_path.write_text("这是一份旧的中文转录内容，而且长度足够用于检测。", encoding="utf-8")
    (tmp_path / "transcript_acquisition.json").write_text(
        json.dumps(
            {
                "source_id": "youtube_course",
                "source_uri": _source().location.uri,
                "goal": "knowledge-ingestion",
                "subtitle_language_preferences": ["zh"],
                "whisper_language": "zh",
                "expected_language": "zh",
                "method": "whisper",
                "language": "zh",
            }
        ),
        encoding="utf-8",
    )
    inspected: list[str] = []

    def whisper(language: str | None) -> WhisperFallbackResult:
        transcript_path.write_text(ENGLISH_TEXT, encoding="utf-8")
        return WhisperFallbackResult(transcript_path)

    coordinator = TranscriptAcquisitionCoordinator(
        subtitle_inspector=lambda source: inspected.append(source) or _inspection(),
        subtitle_extractor=lambda request: pytest.fail("download must not run"),
    )

    result = coordinator.acquire(
        _request(tmp_path, skip_existing=True),
        whisper_fallback=whisper,
    )

    assert result.method is TranscriptAcquisitionMethod.WHISPER
    assert inspected == [_source().location.uri]
    assert result.transcript.text == ENGLISH_TEXT
