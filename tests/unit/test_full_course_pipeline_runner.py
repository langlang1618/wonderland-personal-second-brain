import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_full_course_pipeline import (
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

    def fake_runner(request):
        return SimpleNamespace(
            title="课程A",
            source_type=FullCourseSourceType.M3U8,
            course_dir=tmp_path / "media" / "课程a",
            chunks_dir=tmp_path / "media" / "课程a" / "chunks",
            transcript_dir=tmp_path / "transcripts",
            merged_transcript_path=tmp_path / "transcripts" / "merged_transcript.txt",
            obsidian_note_path=note_path,
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
    chunks_dir.mkdir(parents=True, exist_ok=True)
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
