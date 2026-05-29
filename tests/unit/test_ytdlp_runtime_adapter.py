import subprocess
from pathlib import Path

from ai_knowledge_pipeline.core.source import (
    MediaKind,
    SourceAccess,
    SourceData,
    SourceKind,
    SourceLocation,
)
from ai_knowledge_pipeline.modules.download.contracts import (
    DefaultYtDlpCommandBuilder,
    DownloadProcessOutput,
    DownloadProcessResult,
    MediaDownloadConfig,
    MediaDownloadErrorCode,
    MediaDownloadMode,
    MediaDownloadPlan,
    MediaDownloadRequest,
    MediaDownloadStatus,
    SubprocessYtDlpRunner,
    YtDlpRuntimeAdapter,
    create_default_media_downloader,
    parse_ytdlp_output_path,
)


def youtube_source() -> SourceData:
    return SourceData(
        source_id="src_youtube_adapter",
        kind=SourceKind.YOUTUBE,
        media_kind=MediaKind.VIDEO,
        location=SourceLocation(
            access=SourceAccess.REMOTE,
            uri="https://www.youtube.com/watch?v=adapter",
        ),
    )


def plan() -> MediaDownloadPlan:
    return MediaDownloadPlan(
        source_id="src_youtube_adapter",
        adapter_name="yt-dlp",
        target_path=Path("data/media/src_youtube_adapter.media"),
        temp_path=Path("data/tmp/downloads/src_youtube_adapter"),
        mode=MediaDownloadMode.MATERIALIZE,
    )


class FakeSuccessfulRunner:
    def run(self, command, config):
        return DownloadProcessResult(
            command=command,
            returncode=0,
            output=DownloadProcessOutput(
                stdout="[download] Destination: data/media/result.m4a\n",
                stdout_lines=("[download] Destination: data/media/result.m4a",),
            ),
            parsed_output_path=Path("data/media/result.m4a"),
        )


class FakeFailedRunner:
    def run(self, command, config):
        return DownloadProcessResult(
            command=command,
            returncode=1,
            output=DownloadProcessOutput(
                stderr="network unavailable",
                stderr_lines=("network unavailable",),
            ),
        )


class FakeMissingExecutableRunner:
    def run(self, command, config):
        return DownloadProcessResult(
            command=command,
            returncode=127,
            output=DownloadProcessOutput(stderr="No such file or directory"),
            metadata={"exception": "FileNotFoundError"},
        )


class FakeTimeoutRunner:
    def run(self, command, config):
        return DownloadProcessResult(
            command=command,
            returncode=124,
            output=DownloadProcessOutput(stderr="timed out"),
            metadata={"exception": "TimeoutExpired"},
        )


def test_ytdlp_command_builder_uses_configured_binary_and_plan_paths() -> None:
    command = DefaultYtDlpCommandBuilder().build(
        youtube_source(),
        plan(),
        MediaDownloadConfig(ytdlp_binary="/opt/bin/yt-dlp"),
    )

    assert command[0] == "/opt/bin/yt-dlp"
    assert "--paths" in command
    assert "data/media" in command
    assert "https://www.youtube.com/watch?v=adapter" in command


def test_parse_ytdlp_output_path_prefers_last_materialized_destination() -> None:
    output = "\n".join(
        (
            "[download] Destination: data/media/raw.webm",
            "[ExtractAudio] Destination: data/media/final.m4a",
        )
    )

    assert parse_ytdlp_output_path(output) == Path("data/media/final.m4a")


def test_runtime_adapter_returns_materialized_adapter_result() -> None:
    adapter = YtDlpRuntimeAdapter(runner=FakeSuccessfulRunner())
    result = adapter.download(
        MediaDownloadRequest(source=youtube_source()),
        plan(),
    )

    assert result.is_success
    assert result.path == Path("data/media/result.m4a")
    assert result.metadata["returncode"] == 0
    assert result.metadata["adapter"] == "yt-dlp"


def test_runtime_adapter_maps_nonzero_exit_to_structured_issue() -> None:
    adapter = YtDlpRuntimeAdapter(runner=FakeFailedRunner())
    result = adapter.download(
        MediaDownloadRequest(source=youtube_source()),
        plan(),
    )

    assert not result.is_success
    assert result.issues[0].code is MediaDownloadErrorCode.SUBPROCESS_FAILED
    assert result.issues[0].details["returncode"] == "1"


def test_runtime_adapter_maps_missing_executable_to_structured_issue() -> None:
    adapter = YtDlpRuntimeAdapter(runner=FakeMissingExecutableRunner())
    result = adapter.download(
        MediaDownloadRequest(source=youtube_source()),
        plan(),
    )

    assert not result.is_success
    assert result.issues[0].code is MediaDownloadErrorCode.EXECUTABLE_NOT_FOUND


def test_runtime_adapter_maps_timeout_to_structured_issue() -> None:
    adapter = YtDlpRuntimeAdapter(runner=FakeTimeoutRunner())
    result = adapter.download(
        MediaDownloadRequest(source=youtube_source()),
        plan(),
    )

    assert not result.is_success
    assert result.issues[0].code is MediaDownloadErrorCode.SUBPROCESS_TIMEOUT


def test_subprocess_runner_captures_structured_stdout_and_stderr(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="[download] Destination: data/media/from-runner.mp4\n",
            stderr="warning line\n",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SubprocessYtDlpRunner().run(
        ("yt-dlp", "https://example.test/video"),
        MediaDownloadConfig(),
    )

    assert result.returncode == 0
    assert result.output.stdout_lines == (
        "[download] Destination: data/media/from-runner.mp4",
    )
    assert result.output.stderr_lines == ("warning line",)
    assert result.parsed_output_path == Path("data/media/from-runner.mp4")


def test_subprocess_runner_maps_file_not_found(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("yt-dlp")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SubprocessYtDlpRunner().run(("yt-dlp", "x"), MediaDownloadConfig())

    assert result.returncode == 127
    assert result.metadata["exception"] == "FileNotFoundError"


def test_downloader_materializes_artifact_through_runtime_adapter() -> None:
    adapter = YtDlpRuntimeAdapter(runner=FakeSuccessfulRunner())
    downloader = create_default_media_downloader(remote_adapter=adapter)

    result = downloader.download(MediaDownloadRequest(source=youtube_source()))

    assert result.is_success
    assert result.status is MediaDownloadStatus.DOWNLOADED
    assert result.artifact is not None
    assert result.artifact.path == Path("data/media/result.m4a")
    assert result.artifact.snapshot.lineage.source_id == "src_youtube_adapter"
    assert result.artifact.snapshot.metadata.extra["materialized_path"] == (
        "data/media/result.m4a"
    )
