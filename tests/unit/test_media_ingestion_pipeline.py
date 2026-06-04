import json
from pathlib import Path

from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkProcessOutput,
    ChunkProcessResult,
)
from ai_knowledge_pipeline.modules.download.types import (
    DownloadProcessOutput,
    DownloadProcessResult,
)
from scripts.run_media_ingestion import (
    MediaIngestionRequest,
    MediaIngestionStatus,
    load_urls,
    main,
    run_media_ingestion,
)


class MockYtDlpRunner:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, config):
        self.commands.append(command)
        url = command[-1]
        if self.fail_on and self.fail_on in url:
            return DownloadProcessResult(
                command=command,
                returncode=1,
                output=DownloadProcessOutput(stderr="download failed"),
            )
        output_template = Path(command[command.index("--output") + 1])
        output_path = output_template.with_name(
            output_template.name.replace("%(ext)s", command[command.index("--audio-format") + 1])
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("audio", encoding="utf-8")
        return DownloadProcessResult(
            command=command,
            returncode=0,
            output=DownloadProcessOutput(stdout=str(output_path)),
            parsed_output_path=output_path,
        )


class MockFfmpegRunner:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, config):
        self.commands.append(command)
        input_path = command[command.index("-i") + 1]
        if self.fail_on and self.fail_on in input_path:
            return ChunkProcessResult(
                command=command,
                returncode=1,
                output=ChunkProcessOutput(stderr="chunk failed"),
            )
        pattern = Path(command[-1])
        pattern.parent.mkdir(parents=True, exist_ok=True)
        for index in (1, 2):
            (pattern.parent / f"chunk_{index:03d}.mp3").write_text(
                f"chunk {index}",
                encoding="utf-8",
            )
        return ChunkProcessResult(
            command=command,
            returncode=0,
            output=ChunkProcessOutput(stdout="ok"),
            output_path=pattern.parent / "chunk_001.mp3",
        )


def test_media_ingestion_dry_run_writes_plan_manifest_without_runners(tmp_path) -> None:
    ytdlp = MockYtDlpRunner()
    ffmpeg = MockFfmpegRunner()

    result = run_media_ingestion(
        MediaIngestionRequest(
            urls=("https://example.com/path/course.m3u8?token=secret",),
            output_dir=tmp_path,
            title="课程A",
            dry_run=True,
        ),
        ytdlp_runner=ytdlp,
        ffmpeg_runner=ffmpeg,
    )

    assert result.total == 1
    assert result.items[0].status is MediaIngestionStatus.PLANNED
    assert ytdlp.commands == []
    assert ffmpeg.commands == []
    manifest = json.loads(result.items[0].plan.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_url"] == "https://example.com/path/course.m3u8?token=secret"
    assert manifest["status"] == "planned"
    assert manifest["chunk_minutes"] == 30


def test_media_ingestion_materializes_audio_chunks_and_manifest(tmp_path) -> None:
    result = run_media_ingestion(
        MediaIngestionRequest(
            urls=("https://example.com/course.m3u8",),
            output_dir=tmp_path,
            title="课程A",
            audio_format="mp3",
            chunk_minutes=30,
        ),
        ytdlp_runner=MockYtDlpRunner(),
        ffmpeg_runner=MockFfmpegRunner(),
    )

    assert result.success == 1
    item = result.items[0]
    assert item.plan.downloaded_audio_path.exists()
    assert [path.name for path in item.chunk_paths] == ["chunk_001.mp3", "chunk_002.mp3"]
    manifest = json.loads(item.plan.manifest_path.read_text(encoding="utf-8"))
    assert manifest["downloaded_audio_path"] == str(item.plan.downloaded_audio_path)
    assert manifest["chunk_paths"] == [str(path) for path in item.chunk_paths]
    assert manifest["audio_format"] == "mp3"
    assert manifest["status"] == "materialized"
    assert manifest["errors"] == []


def test_media_ingestion_skip_existing(tmp_path) -> None:
    course_dir = tmp_path / "课程a"
    raw_dir = course_dir / "raw_audio"
    chunks_dir = course_dir / "chunks"
    raw_dir.mkdir(parents=True)
    chunks_dir.mkdir()
    (raw_dir / "course.mp3").write_text("audio", encoding="utf-8")
    (chunks_dir / "chunk_001.mp3").write_text("chunk", encoding="utf-8")
    ytdlp = MockYtDlpRunner()
    ffmpeg = MockFfmpegRunner()

    result = run_media_ingestion(
        MediaIngestionRequest(
            urls=("https://example.com/course.m3u8",),
            output_dir=tmp_path,
            title="课程A",
            skip_existing=True,
        ),
        ytdlp_runner=ytdlp,
        ffmpeg_runner=ffmpeg,
    )

    assert result.items[0].status is MediaIngestionStatus.SKIPPED
    assert result.skipped == 1
    assert ytdlp.commands == []
    assert ffmpeg.commands == []


def test_media_ingestion_url_file_multiple_urls_continue_after_failure(tmp_path) -> None:
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "https://example.com/ok.m3u8\nhttps://example.com/fail.m3u8\n",
        encoding="utf-8",
    )
    urls = load_urls(m3u8=None, url_file=url_file)

    result = run_media_ingestion(
        MediaIngestionRequest(
            urls=urls,
            output_dir=tmp_path / "out",
            title="批量课程",
        ),
        ytdlp_runner=MockYtDlpRunner(fail_on="fail"),
        ffmpeg_runner=MockFfmpegRunner(),
    )

    assert result.total == 2
    assert result.success == 1
    assert result.failed == 1
    assert result.items[0].status is MediaIngestionStatus.MATERIALIZED
    assert result.items[1].status is MediaIngestionStatus.FAILED
    assert "yt-dlp failed" in result.items[1].errors[0]
    failed_manifest = json.loads(
        result.items[1].plan.manifest_path.read_text(encoding="utf-8")
    )
    assert failed_manifest["status"] == "failed"


def test_media_ingestion_ffmpeg_failure_records_clear_error(tmp_path) -> None:
    result = run_media_ingestion(
        MediaIngestionRequest(
            urls=("https://example.com/course.m3u8",),
            output_dir=tmp_path,
            title="课程A",
        ),
        ytdlp_runner=MockYtDlpRunner(),
        ffmpeg_runner=MockFfmpegRunner(fail_on="course.mp3"),
    )

    assert result.failed == 1
    assert result.items[0].status is MediaIngestionStatus.FAILED
    assert "ffmpeg failed" in result.items[0].errors[0]


def test_media_ingestion_cli_dry_run_prints_summary_without_long_query(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "--m3u8",
            "https://example.com/path/course.m3u8?very_long_secret_token=abc123",
            "--output-dir",
            str(tmp_path),
            "--title",
            "课程A",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Media ingestion summary:" in captured.out
    assert "very_long_secret_token" not in captured.out
