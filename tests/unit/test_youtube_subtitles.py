from pathlib import Path

from ai_knowledge_pipeline.modules.download.types import (
    DownloadProcessOutput,
    DownloadProcessResult,
)
from ai_knowledge_pipeline.modules.transcription.runtime.youtube_subtitles import (
    YouTubeSubtitleExtractor,
    YouTubeSubtitleInspector,
    YouTubeSubtitleKind,
    YouTubeSubtitleRequest,
    YouTubeSubtitleStatus,
    build_youtube_subtitle_command,
    build_youtube_subtitle_inspection_command,
    normalize_vtt,
    resolve_ytdlp_executable,
)


class FakeYtDlpRunner:
    def __init__(self, *, returncode: int = 0, subtitle: str | None = None) -> None:
        self.returncode = returncode
        self.subtitle = subtitle
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, config):
        self.commands.append(command)
        if self.subtitle is not None:
            output_template = Path(command[command.index("--output") + 1])
            output_template.parent.mkdir(parents=True, exist_ok=True)
            (output_template.parent / "subtitle.zh-Hans.vtt").write_text(
                self.subtitle,
                encoding="utf-8",
            )
        return DownloadProcessResult(
            command=command,
            returncode=self.returncode,
            output=DownloadProcessOutput(stderr="subtitle unavailable"),
        )


def test_build_command_requests_subtitles_without_media_download(tmp_path) -> None:
    request = YouTubeSubtitleRequest(
        source_url="https://www.youtube.com/watch?v=abc",
        output_dir=tmp_path,
        language="zh",
    )

    command = build_youtube_subtitle_command(request, tmp_path / "subtitles")

    assert "--skip-download" in command
    assert "--write-subs" in command
    assert "--write-auto-subs" in command
    assert "zh-Hans,zh-Hant,zh,en" in command
    assert command[-1] == request.source_url


def test_normalize_vtt_removes_metadata_and_rolling_duplicates() -> None:
    content = """WEBVTT

1
00:00:00.000 --> 00:00:01.000 align:start position:0%
<c>欢迎</c>

2
00:00:01.000 --> 00:00:02.000
欢迎来到课程

3
00:00:02.000 --> 00:00:03.000
欢迎来到课程

4
00:00:03.000 --> 00:00:04.000
今天讨论利率。
"""

    assert normalize_vtt(content) == "欢迎来到课程\n今天讨论利率。"


def test_normalize_vtt_preserves_technical_markup_and_arrow_text() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:02.000
Use <div> and List<T> when A --> B.
"""

    assert normalize_vtt(content) == "Use <div> and List<T> when A --> B."


def test_automatic_vtt_removes_clear_rolling_overlap() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:04.000
All right, gang. Real quick before we get started, this is I'm

00:00:04.000 --> 00:00:08.000
quick before we get started, this is I'm gonna try an experiment
"""

    assert normalize_vtt(content, remove_rolling_overlap=True).splitlines() == [
        "All right, gang. Real quick before we get started, this is I'm",
        "gonna try an experiment",
    ]


def test_automatic_vtt_uses_longest_multiword_overlap() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:04.000
gonna I'm trying an experiment, and that

00:00:04.000 --> 00:00:08.000
gonna I'm trying an experiment, and that is a completely unedited video.
"""

    assert normalize_vtt(content, remove_rolling_overlap=True).splitlines() == [
        "gonna I'm trying an experiment, and that",
        "is a completely unedited video.",
    ]


def test_automatic_vtt_keeps_cue_without_overlap() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:04.000
First independent sentence.

00:00:04.000 --> 00:00:08.000
Second unrelated sentence.
"""

    assert normalize_vtt(content, remove_rolling_overlap=True).splitlines() == [
        "First independent sentence.",
        "Second unrelated sentence.",
    ]


def test_automatic_vtt_preserves_legitimate_short_repetition() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:04.000
This is important.

00:00:04.000 --> 00:00:08.000
Important. Important choices require context.
"""

    assert normalize_vtt(content, remove_rolling_overlap=True).splitlines() == [
        "This is important.",
        "Important. Important choices require context.",
    ]


def test_automatic_vtt_matches_overlap_across_punctuation() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:04.000
Start with the model, then deploy.

00:00:04.000 --> 00:00:08.000
the model then deploy; and monitor it.
"""

    assert normalize_vtt(content, remove_rolling_overlap=True).splitlines() == [
        "Start with the model, then deploy.",
        "and monitor it.",
    ]


def test_manual_vtt_does_not_apply_rolling_overlap_cleanup() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:04.000
real quick before we get started, this is I'm

00:00:04.000 --> 00:00:08.000
quick before we get started, this is I'm gonna continue
"""

    assert normalize_vtt(content).splitlines() == [
        "real quick before we get started, this is I'm",
        "quick before we get started, this is I'm gonna continue",
    ]


def test_automatic_vtt_preserves_technical_text() -> None:
    content = """WEBVTT

00:00:00.000 --> 00:00:04.000
Use <div> and List<T> in A --> B mappings.

00:00:04.000 --> 00:00:08.000
Then render the result without rewriting it.
"""

    normalized = normalize_vtt(content, remove_rolling_overlap=True)

    assert "<div>" in normalized
    assert "List<T>" in normalized
    assert "A --> B" in normalized


def test_manual_and_automatic_commands_are_distinct(tmp_path) -> None:
    manual = build_youtube_subtitle_command(
        YouTubeSubtitleRequest(
            source_url="https://youtu.be/abc",
            output_dir=tmp_path,
            language="en",
            subtitle_kind=YouTubeSubtitleKind.MANUAL,
        ),
        tmp_path,
    )
    automatic = build_youtube_subtitle_command(
        YouTubeSubtitleRequest(
            source_url="https://youtu.be/abc",
            output_dir=tmp_path,
            language="en",
            subtitle_kind=YouTubeSubtitleKind.AUTOMATIC,
        ),
        tmp_path,
    )

    assert "--write-subs" in manual
    assert "--write-auto-subs" not in manual
    assert manual[manual.index("--sub-langs") + 1] == "en"
    assert "--write-auto-subs" in automatic
    assert "--write-subs" not in automatic
    assert automatic[automatic.index("--sub-langs") + 1] == "en"


def test_inspector_reads_manual_and_automatic_languages_from_json(tmp_path) -> None:
    executable = tmp_path / "yt-dlp"
    executable.write_text("test", encoding="utf-8")
    executable.chmod(0o755)

    class InspectionRunner:
        def run(self, command, config):
            stdout = (
                "2026.08.19\n"
                if "--version" in command
                else '{"subtitles":{"en":[]},"automatic_captions":{"en-US":[],"zh":[]}}'
            )
            return DownloadProcessResult(
                command=command,
                returncode=0,
                output=DownloadProcessOutput(stdout=stdout),
            )

    result = YouTubeSubtitleInspector(InspectionRunner()).inspect(
        "https://youtu.be/abc",
        ytdlp_binary=str(executable),
    )

    assert result.manual_languages == ("en",)
    assert result.automatic_languages == ("en-US", "zh")
    assert result.executable == str(executable.resolve())
    assert result.version == "2026.08.19"
    assert build_youtube_subtitle_inspection_command("url", "binary") == (
        "binary",
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        "url",
    )


def test_ytdlp_resolution_accepts_an_explicit_runtime_binary(tmp_path) -> None:
    executable = tmp_path / "yt-dlp"
    executable.write_text("test", encoding="utf-8")
    executable.chmod(0o755)

    assert resolve_ytdlp_executable(str(executable)) == str(executable.resolve())


def test_extractor_writes_existing_transcript_handoff(tmp_path) -> None:
    runner = FakeYtDlpRunner(
        subtitle="""WEBVTT

00:00:00.000 --> 00:00:01.000
第一段字幕。
"""
    )

    result = YouTubeSubtitleExtractor(runner).extract(
        YouTubeSubtitleRequest(
            source_url="https://youtu.be/abc",
            output_dir=tmp_path,
        )
    )

    assert result.status is YouTubeSubtitleStatus.AVAILABLE
    assert result.transcript_path == tmp_path / "merged_transcript.txt"
    assert result.transcript_path.read_text(encoding="utf-8") == "第一段字幕。\n"


def test_extractor_reports_unavailable_without_subtitle_file(tmp_path) -> None:
    result = YouTubeSubtitleExtractor(FakeYtDlpRunner()).extract(
        YouTubeSubtitleRequest(
            source_url="https://youtu.be/abc",
            output_dir=tmp_path,
        )
    )

    assert result.status is YouTubeSubtitleStatus.UNAVAILABLE
    assert result.transcript_path is None


def test_extractor_maps_ytdlp_error_to_failed_result(tmp_path) -> None:
    result = YouTubeSubtitleExtractor(FakeYtDlpRunner(returncode=1)).extract(
        YouTubeSubtitleRequest(
            source_url="https://youtu.be/abc",
            output_dir=tmp_path,
        )
    )

    assert result.status is YouTubeSubtitleStatus.FAILED
    assert "subtitle unavailable" in (result.message or "")


def test_extractor_does_not_reuse_stale_subtitle_after_failed_attempt(tmp_path) -> None:
    subtitle_dir = tmp_path / "youtube_subtitles"
    subtitle_dir.mkdir()
    (subtitle_dir / "subtitle.zh-Hans.vtt").write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n旧字幕\n",
        encoding="utf-8",
    )

    result = YouTubeSubtitleExtractor(FakeYtDlpRunner(returncode=1)).extract(
        YouTubeSubtitleRequest(
            source_url="https://youtu.be/new-video",
            output_dir=tmp_path,
        )
    )

    assert result.status is YouTubeSubtitleStatus.FAILED
    assert result.transcript_path is None
