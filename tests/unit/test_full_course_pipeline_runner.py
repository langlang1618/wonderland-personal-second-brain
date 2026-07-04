import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_knowledge_pipeline.infra.runtime_logging import create_runtime_logger
from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkProcessOutput,
    ChunkProcessResult,
)
from scripts.run_full_course_pipeline import (
    CleanupSelection,
    FullCoursePipelineError,
    FullCoursePipelineRequest,
    FullCourseSourceType,
    _parse_args,
    main,
    run_full_course_pipeline,
)
from scripts.run_local_whisper_transcription import LocalWhisperRuntimeResult
from scripts.run_media_ingestion import (
    MediaIngestionBatchResult,
    MediaIngestionItemResult,
    MediaIngestionPlan,
    MediaIngestionStatus,
)


class FakeFfmpegRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, config):
        self.commands.append(command)
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if "%" in output_path.name:
            for index in (1, 2):
                (output_path.parent / f"chunk_{index:03d}.mp3").write_text(
                    f"chunk {index}",
                    encoding="utf-8",
                )
        else:
            output_path.write_text("audio", encoding="utf-8")
        return ChunkProcessResult(
            command=command,
            returncode=0,
            output=ChunkProcessOutput(stdout="ok"),
            output_path=output_path,
        )


class FailingFfmpegRunner:
    def run(self, command, config):
        return ChunkProcessResult(
            command=command,
            returncode=1,
            output=ChunkProcessOutput(stderr="ffmpeg failed"),
        )


def test_full_course_pipeline_help_runs(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        _parse_args(["--help"])

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "Run one source through ingestion" in captured.out


def test_full_course_pipeline_source_is_required() -> None:
    with pytest.raises(SystemExit) as exc:
        _parse_args([])

    assert exc.value.code == 2


def test_full_course_pipeline_dry_run_plans_without_whisper_or_deepseek(tmp_path) -> None:
    calls: list[str] = []

    def fake_media_runner(request):
        calls.append("media")
        assert request.dry_run is True
        assert request.urls == ("https://example.com/course.m3u8?token=secret",)
        return _media_result(tmp_path, status=MediaIngestionStatus.PLANNED)

    def fake_whisper_runner(request):
        calls.append("whisper")
        raise AssertionError("dry-run must not transcribe")

    def fake_course_runner(request):
        calls.append("course")
        raise AssertionError("dry-run must not clean or write")

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source="https://example.com/course.m3u8?token=secret",
            title="课程A",
            dry_run=True,
            output_dir=tmp_path / "media",
            transcript_output_dir=tmp_path / "transcripts",
        ),
        media_ingestion_runner=fake_media_runner,
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
    )

    assert calls == ["media"]
    assert result.dry_run is True
    assert result.title == "课程A"
    assert result.chunks_dir == tmp_path / "media" / "课程a" / "chunks"
    assert result.merged_transcript_path == tmp_path / "transcripts" / "merged_transcript.txt"
    assert result.obsidian_note_path is None
    assert result.cleanup == "none"


def test_full_course_pipeline_local_audio_dry_run_generates_plan(tmp_path) -> None:
    source = tmp_path / "course.mp3"
    source.write_text("audio", encoding="utf-8")
    ffmpeg = FakeFfmpegRunner()

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_AUDIO,
            title="本地音频",
            dry_run=True,
            output_dir=tmp_path / "media",
            transcript_output_dir=tmp_path / "transcripts",
        ),
        ffmpeg_runner=ffmpeg,
    )

    assert result.dry_run is True
    assert result.course_dir == tmp_path / "media" / "本地音频"
    assert result.raw_audio_path == tmp_path / "media" / "本地音频" / "raw_audio" / "course.mp3"
    assert result.chunks_dir == tmp_path / "media" / "本地音频" / "chunks"
    assert result.merged_transcript_path == tmp_path / "transcripts" / "merged_transcript.txt"
    assert result.obsidian_note_path is None
    assert ffmpeg.commands == []


def test_full_course_pipeline_cleanup_raw_dry_run_plans_without_deleting(tmp_path) -> None:
    source = tmp_path / "course.mp3"
    source.write_text("audio", encoding="utf-8")
    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_AUDIO,
            title="本地音频",
            dry_run=True,
            cleanup=CleanupSelection.RAW.value,
            output_dir=tmp_path / "media",
        ),
        ffmpeg_runner=FakeFfmpegRunner(),
    )

    assert result.cleanup == "raw"
    assert result.cleanup_plan == (
        f"would remove {tmp_path / 'media' / '本地音频' / 'raw_audio'}",
    )
    assert source.exists()


def test_full_course_pipeline_cleanup_chunks_dry_run_plans_without_deleting(tmp_path) -> None:
    source = tmp_path / "course.mp4"
    source.write_text("video", encoding="utf-8")
    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_VIDEO,
            dry_run=True,
            cleanup=CleanupSelection.CHUNKS.value,
            output_dir=tmp_path / "media",
        ),
        ffmpeg_runner=FakeFfmpegRunner(),
    )

    assert result.cleanup == "chunks"
    assert result.cleanup_plan == (
        f"would remove {tmp_path / 'media' / 'course' / 'chunks'}",
    )
    assert source.exists()


def test_full_course_pipeline_cleanup_raw_chunks_dry_run_plans_both(tmp_path) -> None:
    source = tmp_path / "course.mp4"
    source.write_text("video", encoding="utf-8")
    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_VIDEO,
            dry_run=True,
            cleanup=CleanupSelection.RAW_CHUNKS.value,
            output_dir=tmp_path / "media",
        ),
        ffmpeg_runner=FakeFfmpegRunner(),
    )

    assert result.cleanup_plan == (
        f"would remove {tmp_path / 'media' / 'course' / 'raw_audio'}",
        f"would remove {tmp_path / 'media' / 'course' / 'chunks'}",
    )


def test_full_course_pipeline_local_video_dry_run_generates_plan(tmp_path) -> None:
    source = tmp_path / "course.mp4"
    source.write_text("video", encoding="utf-8")
    ffmpeg = FakeFfmpegRunner()

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_VIDEO,
            dry_run=True,
            output_dir=tmp_path / "media",
        ),
        ffmpeg_runner=ffmpeg,
    )

    assert result.dry_run is True
    assert result.title == "course"
    assert result.raw_audio_path == tmp_path / "media" / "course" / "raw_audio" / "course.mp3"
    assert result.chunks_dir == tmp_path / "media" / "course" / "chunks"
    assert result.obsidian_note_path is None
    assert ffmpeg.commands == []


def test_full_course_pipeline_orchestrates_existing_runners_in_order(tmp_path) -> None:
    calls: list[str] = []
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    transcript_dir = tmp_path / "transcripts"
    note_path = vault_path / "课程A.md"

    def fake_media_runner(request):
        calls.append("media")
        assert request.title == "课程A"
        assert request.chunk_minutes == 45
        return _media_result(tmp_path, chunk_count=2)

    def fake_whisper_runner(request):
        calls.append("whisper")
        assert request.chunks_dir == tmp_path / "media" / "课程a" / "chunks"
        assert request.output_dir == transcript_dir
        assert request.model_size == "small"
        assert request.language == "zh"
        assert request.merge is True
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    def fake_course_runner(request):
        calls.append("course")
        assert request.local_transcript_path == transcript_dir / "merged_transcript.txt"
        assert request.obsidian_vault_path == vault_path
        assert request.title == "课程A"
        assert request.tags == ("金融学习", "课程")
        assert request.profile == "finance"
        assert request.model == "deepseek-v4-flash"
        return SimpleNamespace(obsidian_note_path=note_path)

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source="https://example.com/course.m3u8",
            title="课程A",
            profile="finance",
            tags=("金融学习", "课程"),
            chunk_minutes=45,
            vault_path=vault_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=transcript_dir,
        ),
        media_ingestion_runner=fake_media_runner,
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
    )

    assert calls == ["media", "whisper", "course"]
    assert result.course_dir == tmp_path / "media" / "课程a"
    assert result.chunks_dir == tmp_path / "media" / "课程a" / "chunks"
    assert result.transcript_dir == transcript_dir
    assert result.merged_transcript_path == transcript_dir / "merged_transcript.txt"
    assert result.obsidian_note_path == note_path
    assert result.cleanup == "none"


def test_full_course_pipeline_passes_shared_logger_to_supported_runners(tmp_path) -> None:
    logger = create_runtime_logger()
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    transcript_dir = tmp_path / "transcripts"

    def fake_media_runner(request, logger):
        with logger.stage("Audio Extraction"):
            pass
        return _media_result(tmp_path)

    def fake_whisper_runner(request, logger):
        with logger.stage("Whisper Transcription"):
            pass
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    def fake_course_runner(request, logger):
        with logger.stage("Markdown Generation"):
            pass
        return SimpleNamespace(obsidian_note_path=vault_path / "note.md")

    run_full_course_pipeline(
        FullCoursePipelineRequest(
            source="https://example.com/course.m3u8",
            title="课程A",
            vault_path=vault_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=transcript_dir,
        ),
        media_ingestion_runner=fake_media_runner,
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
        logger=logger,
    )

    stage_names = [metric.stage_name for metric in logger.metrics.stage_metrics()]
    assert "Profile Loading" in stage_names
    assert "Audio Extraction" in stage_names
    assert "Whisper Transcription" in stage_names
    assert "Markdown Generation" in stage_names


def test_full_course_pipeline_local_audio_orchestrates_to_whisper_and_obsidian(tmp_path) -> None:
    calls: list[str] = []
    source = tmp_path / "course.m4a"
    source.write_text("audio", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    ffmpeg = FakeFfmpegRunner()

    def fake_whisper_runner(request):
        calls.append("whisper")
        assert request.chunks_dir == tmp_path / "media" / "课程a" / "chunks"
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    def fake_course_runner(request):
        calls.append("course")
        assert request.local_transcript_path.name == "merged_transcript.txt"
        assert request.obsidian_vault_path == vault_path
        return SimpleNamespace(obsidian_note_path=vault_path / "课程A.md")

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_AUDIO,
            title="课程A",
            vault_path=vault_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=tmp_path / "transcripts",
        ),
        ffmpeg_runner=ffmpeg,
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
    )

    assert calls == ["whisper", "course"]
    assert result.raw_audio_path == tmp_path / "media" / "课程a" / "raw_audio" / "course.m4a"
    assert result.raw_audio_path.exists()
    assert [command[0] for command in ffmpeg.commands] == ["ffmpeg"]
    assert result.obsidian_note_path == vault_path / "课程A.md"


def test_full_course_pipeline_cleanup_raw_after_success_removes_raw_audio(tmp_path) -> None:
    result, source, transcript_dir, note_path = _run_successful_local_audio(
        tmp_path,
        cleanup=CleanupSelection.RAW.value,
    )

    assert result.cleanup_removed == (tmp_path / "media" / "课程a" / "raw_audio",)
    assert not (tmp_path / "media" / "课程a" / "raw_audio").exists()
    assert (tmp_path / "media" / "课程a" / "chunks").exists()
    assert transcript_dir.exists()
    assert note_path.exists()
    assert source.exists()


def test_full_course_pipeline_cleanup_chunks_after_success_removes_chunks(tmp_path) -> None:
    result, source, transcript_dir, note_path = _run_successful_local_audio(
        tmp_path,
        cleanup=CleanupSelection.CHUNKS.value,
    )

    assert result.cleanup_removed == (tmp_path / "media" / "课程a" / "chunks",)
    assert (tmp_path / "media" / "课程a" / "raw_audio").exists()
    assert not (tmp_path / "media" / "课程a" / "chunks").exists()
    assert transcript_dir.exists()
    assert note_path.exists()
    assert source.exists()


def test_full_course_pipeline_cleanup_raw_chunks_after_success_removes_both(tmp_path) -> None:
    result, source, transcript_dir, note_path = _run_successful_local_audio(
        tmp_path,
        cleanup=CleanupSelection.RAW_CHUNKS.value,
    )

    assert result.cleanup_removed == (
        tmp_path / "media" / "课程a" / "raw_audio",
        tmp_path / "media" / "课程a" / "chunks",
    )
    assert not (tmp_path / "media" / "课程a" / "raw_audio").exists()
    assert not (tmp_path / "media" / "课程a" / "chunks").exists()
    assert transcript_dir.exists()
    assert note_path.exists()
    assert source.exists()


def test_full_course_pipeline_cleanup_all_media_removes_raw_and_chunks(tmp_path) -> None:
    result, source, transcript_dir, note_path = _run_successful_local_audio(
        tmp_path,
        cleanup=CleanupSelection.ALL_MEDIA.value,
    )

    assert result.cleanup == "all-media"
    assert not (tmp_path / "media" / "课程a" / "raw_audio").exists()
    assert not (tmp_path / "media" / "课程a" / "chunks").exists()
    assert transcript_dir.exists()
    assert note_path.exists()
    assert source.exists()


def test_full_course_pipeline_failure_does_not_cleanup(tmp_path) -> None:
    source = tmp_path / "course.mp3"
    source.write_text("audio", encoding="utf-8")

    def fake_whisper_runner(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    def failing_course_runner(request):
        raise RuntimeError("downstream failed")

    with pytest.raises(RuntimeError):
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source=str(source),
                source_type=FullCourseSourceType.LOCAL_AUDIO,
                title="课程A",
                vault_path=tmp_path,
                output_dir=tmp_path / "media",
                transcript_output_dir=tmp_path / "transcripts",
                cleanup=CleanupSelection.RAW_CHUNKS.value,
            ),
            ffmpeg_runner=FakeFfmpegRunner(),
            whisper_runner=fake_whisper_runner,
            course_runner=failing_course_runner,
        )

    assert (tmp_path / "media" / "课程a" / "raw_audio").exists()
    assert (tmp_path / "media" / "课程a" / "chunks").exists()


def test_full_course_pipeline_local_video_orchestrates_to_whisper_and_obsidian(tmp_path) -> None:
    calls: list[str] = []
    source = tmp_path / "course.mp4"
    source.write_text("video", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    ffmpeg = FakeFfmpegRunner()

    def fake_whisper_runner(request):
        calls.append("whisper")
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    def fake_course_runner(request):
        calls.append("course")
        return SimpleNamespace(obsidian_note_path=vault_path / "course.md")

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_VIDEO,
            vault_path=vault_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=tmp_path / "transcripts",
        ),
        ffmpeg_runner=ffmpeg,
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
    )

    assert calls == ["whisper", "course"]
    assert result.title == "course"
    assert result.raw_audio_path == tmp_path / "media" / "course" / "raw_audio" / "course.mp3"
    assert len(ffmpeg.commands) == 2
    assert "-vn" in ffmpeg.commands[0]
    assert result.obsidian_note_path == vault_path / "course.md"


def test_full_course_pipeline_ts_auto_detects_as_local_video(tmp_path) -> None:
    source = tmp_path / "course.ts"
    source.write_text("video", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    ffmpeg = FakeFfmpegRunner()

    def fake_whisper_runner(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            vault_path=vault_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=tmp_path / "transcripts",
        ),
        ffmpeg_runner=ffmpeg,
        whisper_runner=fake_whisper_runner,
        course_runner=lambda request: SimpleNamespace(
            obsidian_note_path=vault_path / "course.md"
        ),
    )

    assert result.source_type is FullCourseSourceType.LOCAL_VIDEO
    assert result.raw_audio_path == tmp_path / "media" / "course" / "raw_audio" / "course.mp3"
    assert len(ffmpeg.commands) == 2
    assert "-vn" in ffmpeg.commands[0]


def test_full_course_pipeline_local_skip_existing_reuses_chunks(tmp_path) -> None:
    calls: list[str] = []
    source = tmp_path / "course.mp3"
    source.write_text("audio", encoding="utf-8")
    raw_audio_path = tmp_path / "media" / "课程a" / "raw_audio" / "course.mp3"
    chunks_dir = tmp_path / "media" / "课程a" / "chunks"
    raw_audio_path.parent.mkdir(parents=True)
    chunks_dir.mkdir(parents=True)
    raw_audio_path.write_text("existing audio", encoding="utf-8")
    (chunks_dir / "chunk_001.mp3").write_text("existing chunk", encoding="utf-8")
    ffmpeg = FakeFfmpegRunner()

    def fake_whisper_runner(request):
        calls.append("whisper")
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_AUDIO,
            title="课程A",
            vault_path=tmp_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=tmp_path / "transcripts",
            skip_existing=True,
        ),
        ffmpeg_runner=ffmpeg,
        whisper_runner=fake_whisper_runner,
        course_runner=lambda request: SimpleNamespace(obsidian_note_path=tmp_path / "note.md"),
    )

    assert calls == ["whisper"]
    assert ffmpeg.commands == []
    assert result.raw_audio_path == raw_audio_path


def test_full_course_pipeline_skip_existing_reuses_merged_transcript_without_whisper(
    tmp_path,
) -> None:
    calls: list[str] = []
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    merged = transcript_dir / "merged_transcript.txt"
    merged.write_text("existing merged transcript", encoding="utf-8")

    def fake_whisper_runner(request):
        raise AssertionError("existing merged transcript should skip transcription")

    def fake_course_runner(request):
        calls.append("course")
        assert request.local_transcript_path == merged
        return SimpleNamespace(obsidian_note_path=tmp_path / "note.md")

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source="https://example.com/course.m3u8",
            title="课程A",
            vault_path=tmp_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=transcript_dir,
            skip_existing=True,
        ),
        media_ingestion_runner=lambda request: _media_result(tmp_path, chunk_count=2),
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
    )

    assert calls == ["course"]
    assert result.merged_transcript_path == merged
    assert result.obsidian_note_path == tmp_path / "note.md"


def test_full_course_pipeline_continues_when_whisper_has_partial_warnings(
    tmp_path,
) -> None:
    calls: list[str] = []
    transcript_dir = tmp_path / "transcripts"
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    def fake_whisper_runner(request, logger):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("usable transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(SimpleNamespace(text_path=request.output_dir / "chunk_001.txt"),),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
            errors=("chunk_002.mp3: empty transcript",),
        )

    def fake_course_runner(request, logger):
        calls.append("course")
        assert request.local_transcript_path == transcript_dir / "merged_transcript.txt"
        return SimpleNamespace(obsidian_note_path=vault_path / "note.md")

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source="https://example.com/course.m3u8",
            title="课程A",
            vault_path=vault_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=transcript_dir,
        ),
        media_ingestion_runner=lambda request: _media_result(tmp_path, chunk_count=2),
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
    )

    assert calls == ["course"]
    assert result.obsidian_note_path == vault_path / "note.md"


def test_full_course_pipeline_fails_when_whisper_produces_no_usable_text(
    tmp_path,
) -> None:
    def fake_whisper_runner(request, logger):
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=None,
            manifest_path=request.output_dir / "manifest.json",
            errors=("chunk_001.mp3: empty transcript", "chunk_002.mp3: empty transcript"),
        )

    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source="https://example.com/course.m3u8",
                title="课程A",
                vault_path=tmp_path,
                output_dir=tmp_path / "media",
                transcript_output_dir=tmp_path / "transcripts",
            ),
            media_ingestion_runner=lambda request: _media_result(tmp_path, chunk_count=2),
            whisper_runner=fake_whisper_runner,
        )

    assert "Whisper transcription produced no usable transcript text" in str(exc.value)


def test_full_course_pipeline_local_video_ffmpeg_failure_reports_error(tmp_path) -> None:
    source = tmp_path / "course.mp4"
    source.write_text("video", encoding="utf-8")

    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source=str(source),
                source_type=FullCourseSourceType.LOCAL_VIDEO,
                output_dir=tmp_path / "media",
            ),
            ffmpeg_runner=FailingFfmpegRunner(),
        )

    assert "ffmpeg audio extraction failed" in str(exc.value)
    assert "ffmpeg failed" in str(exc.value)


def test_full_course_pipeline_title_is_optional(tmp_path) -> None:
    def fake_media_runner(request):
        assert request.title == "course"
        return _media_result(tmp_path, title="course")

    def fake_whisper_runner(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source="https://example.com/course.m3u8",
            vault_path=tmp_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=tmp_path / "transcripts",
        ),
        media_ingestion_runner=fake_media_runner,
        whisper_runner=fake_whisper_runner,
        course_runner=lambda request: SimpleNamespace(obsidian_note_path=tmp_path / "note.md"),
    )

    assert result.title == "course"
    assert result.source_type is FullCourseSourceType.M3U8


def test_full_course_pipeline_invalid_cleanup_value_reports_error(tmp_path) -> None:
    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source="https://example.com/course.m3u8",
                cleanup="everything",
                dry_run=True,
            ),
            media_ingestion_runner=lambda request: _media_result(tmp_path),
        )

    assert "Invalid cleanup policy" in str(exc.value)


def test_full_course_pipeline_cli_rejects_invalid_cleanup() -> None:
    with pytest.raises(SystemExit) as exc:
        _parse_args(
            [
                "--source",
                "https://example.com/course.m3u8",
                "--cleanup",
                "everything",
            ]
        )

    assert exc.value.code == 2


def test_full_course_pipeline_local_audio_missing_source_reports_clear_error(tmp_path) -> None:
    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source=str(tmp_path / "missing.mp3"),
                source_type=FullCourseSourceType.LOCAL_AUDIO,
                dry_run=True,
            )
        )

    assert "local source does not exist" in str(exc.value)


def test_full_course_pipeline_local_video_missing_source_reports_clear_error(tmp_path) -> None:
    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source=str(tmp_path / "missing.mp4"),
                source_type=FullCourseSourceType.LOCAL_VIDEO,
                dry_run=True,
            )
        )

    assert "local source does not exist" in str(exc.value)


def test_full_course_pipeline_local_audio_unsupported_extension(tmp_path) -> None:
    source = tmp_path / "course.txt"
    source.write_text("not audio", encoding="utf-8")

    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source=str(source),
                source_type=FullCourseSourceType.LOCAL_AUDIO,
                dry_run=True,
            )
        )

    assert "Unsupported local-audio extension" in str(exc.value)


def test_full_course_pipeline_local_video_unsupported_extension(tmp_path) -> None:
    source = tmp_path / "course.txt"
    source.write_text("not video", encoding="utf-8")

    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source=str(source),
                source_type=FullCourseSourceType.LOCAL_VIDEO,
                dry_run=True,
            )
        )

    assert "Unsupported local-video extension" in str(exc.value)


def test_full_course_pipeline_reports_missing_chunks(tmp_path) -> None:
    with pytest.raises(FullCoursePipelineError) as exc:
        run_full_course_pipeline(
            FullCoursePipelineRequest(
                source="https://example.com/course.m3u8",
                vault_path=tmp_path,
                output_dir=tmp_path / "media",
            ),
            media_ingestion_runner=lambda request: _media_result(tmp_path, chunk_count=0),
        )

    assert "No audio chunks" in str(exc.value)


def test_full_course_pipeline_main_prints_obsidian_note_path(monkeypatch, tmp_path, capsys) -> None:
    note_path = tmp_path / "vault" / "note.md"
    chunks_dir = tmp_path / "media" / "课程a" / "chunks"
    chunks_dir.mkdir(parents=True)
    (chunks_dir / "chunk_001.mp3").write_text("chunk", encoding="utf-8")

    def fake_runner(request, **kwargs):
        return SimpleNamespace(
            title="课程A",
            source_type=FullCourseSourceType.M3U8,
            course_dir=tmp_path / "media" / "课程a",
            raw_audio_path=tmp_path / "media" / "课程a" / "raw_audio" / "course.mp3",
            chunks_dir=chunks_dir,
            transcript_dir=tmp_path / "transcripts",
            merged_transcript_path=tmp_path / "transcripts" / "merged_transcript.txt",
            obsidian_note_path=note_path,
            cleanup="none",
            cleanup_removed=(),
            cleanup_skipped=(),
            cleanup_plan=(),
            dry_run=False,
        )

    monkeypatch.setattr(
        "scripts.run_full_course_pipeline.run_full_course_pipeline",
        fake_runner,
    )

    exit_code = main(
        [
            "--source",
            "https://example.com/course.m3u8",
            "--vault",
            str(tmp_path / "vault"),
            "--title",
            "课程A",
            "--tags",
            "金融学习,课程",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "obsidian_note_path:" in captured.out
    assert str(note_path) in captured.out
    assert "Wonderland Pipeline Summary" in captured.out
    assert "Course\n课程A" in captured.out
    assert "Chunks\n1" in captured.out


def _media_result(
    tmp_path: Path,
    *,
    title: str = "课程A",
    status: MediaIngestionStatus = MediaIngestionStatus.MATERIALIZED,
    chunk_count: int = 1,
) -> MediaIngestionBatchResult:
    course_dir = tmp_path / "media" / _slugify(title)
    raw_dir = course_dir / "raw_audio"
    chunks_dir = course_dir / "chunks"
    raw_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "course.mp3").write_text("audio", encoding="utf-8")
    chunk_paths = tuple(chunks_dir / f"chunk_{index:03d}.mp3" for index in range(1, chunk_count + 1))
    for path in chunk_paths:
        path.write_text("audio", encoding="utf-8")
    plan = MediaIngestionPlan(
        source_url="https://example.com/course.m3u8",
        title=title,
        course_dir=course_dir,
        raw_audio_dir=raw_dir,
        chunks_dir=chunks_dir,
        manifest_path=course_dir / "manifest.json",
        downloaded_audio_path=raw_dir / "course.mp3",
        chunk_pattern=chunks_dir / "chunk_%03d.mp3",
        download_command=("yt-dlp", "https://example.com/course.m3u8"),
        chunk_command=("ffmpeg",),
    )
    return MediaIngestionBatchResult(
        items=(
            MediaIngestionItemResult(
                index=1,
                plan=plan,
                status=status,
                chunk_paths=chunk_paths,
            ),
        )
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-").lower()


def _run_successful_local_audio(
    tmp_path: Path,
    *,
    cleanup: str,
):
    source = tmp_path / "source.mp3"
    source.write_text("source audio", encoding="utf-8")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    note_path = vault_path / "课程A.md"
    transcript_dir = tmp_path / "transcripts"

    def fake_whisper_runner(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        merged = request.output_dir / "merged_transcript.txt"
        merged.write_text("merged transcript", encoding="utf-8")
        return LocalWhisperRuntimeResult(
            chunk_transcripts=(),
            merged_transcript_path=merged,
            manifest_path=request.output_dir / "manifest.json",
        )

    def fake_course_runner(request):
        note_path.write_text("obsidian note", encoding="utf-8")
        return SimpleNamespace(obsidian_note_path=note_path)

    result = run_full_course_pipeline(
        FullCoursePipelineRequest(
            source=str(source),
            source_type=FullCourseSourceType.LOCAL_AUDIO,
            title="课程A",
            vault_path=vault_path,
            output_dir=tmp_path / "media",
            transcript_output_dir=transcript_dir,
            cleanup=cleanup,
        ),
        ffmpeg_runner=FakeFfmpegRunner(),
        whisper_runner=fake_whisper_runner,
        course_runner=fake_course_runner,
    )
    return result, source, transcript_dir, note_path
