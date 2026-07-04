import json
from io import StringIO
from pathlib import Path

from ai_knowledge_pipeline.infra.runtime_logging import create_runtime_logger
from ai_knowledge_pipeline.modules.transcription import FasterWhisperProvider
from scripts.run_local_whisper_transcription import (
    LocalWhisperRuntimeRequest,
    scan_chunk_files,
    run_local_whisper_transcription,
)
from tests.unit.test_faster_whisper_provider import FakeModel
from tests.unit.test_faster_whisper_provider import Info, Segment


class PerFileTextModel:
    def __init__(self, text_by_name):
        self.text_by_name = text_by_name

    def transcribe(self, audio, **kwargs):
        text = self.text_by_name.get(Path(audio).name, "")
        return (Segment(0.0, 1.0, text),), Info()


def test_scan_chunk_files_uses_natural_order(tmp_path) -> None:
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    for name in ("chunk_010.mp3", "chunk_002.mp3", "chunk_001.mp3"):
        (chunks_dir / name).write_text("audio", encoding="utf-8")

    paths = scan_chunk_files(chunks_dir)

    assert [path.name for path in paths] == ["chunk_001.mp3", "chunk_002.mp3", "chunk_010.mp3"]


def test_real_whisper_runtime_writes_chunk_txt_merge_and_manifest(tmp_path) -> None:
    chunks_dir = tmp_path / "course" / "chunks"
    chunks_dir.mkdir(parents=True)
    for index in (1, 2):
        (chunks_dir / f"chunk_{index:03d}.mp3").write_text("audio", encoding="utf-8")
    output_dir = tmp_path / "transcripts"
    provider = FasterWhisperProvider(model_factory=lambda model_size, **kwargs: FakeModel())

    result = run_local_whisper_transcription(
        LocalWhisperRuntimeRequest(
            chunks_dir=chunks_dir,
            output_dir=output_dir,
            model_size="small",
            language="zh",
            merge=True,
        ),
        provider=provider,
    )

    assert len(result.chunk_transcripts) == 2
    assert (output_dir / "chunk_001.txt").exists()
    assert (output_dir / "chunk_002.txt").exists()
    assert result.merged_transcript_path == output_dir / "merged_transcript.txt"
    assert result.merged_transcript_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["model"] == "small"
    assert manifest["language"] == "zh"
    assert manifest["chunk_count"] == 2
    assert len(manifest["transcript_files"]) == 2
    assert manifest["merged_transcript_path"] == str(output_dir / "merged_transcript.txt")
    assert manifest["errors"] == []


def test_real_whisper_runtime_logs_chunk_progress(tmp_path) -> None:
    chunks_dir = tmp_path / "course" / "chunks"
    chunks_dir.mkdir(parents=True)
    for index in (1, 2):
        (chunks_dir / f"chunk_{index:03d}.mp3").write_text("audio", encoding="utf-8")
    output_dir = tmp_path / "transcripts"
    provider = FasterWhisperProvider(model_factory=lambda model_size, **kwargs: FakeModel())
    stream = StringIO()
    logger = create_runtime_logger(stream)

    run_local_whisper_transcription(
        LocalWhisperRuntimeRequest(chunks_dir=chunks_dir, output_dir=output_dir),
        provider=provider,
        logger=logger,
    )

    output = stream.getvalue()
    assert "[INFO] Whisper Transcription started" in output
    assert "[PROGRESS] Whisper Transcription | Chunk 1 / 2: chunk_001.mp3 started" in output
    assert "[SUCCESS] Whisper Transcription | Chunk 1 / 2: chunk_001.mp3 finished" in output
    assert "[PROGRESS] Whisper Transcription | Chunk 2 / 2: chunk_002.mp3 started" in output
    assert "[SUCCESS] Whisper Transcription | Chunk 2 / 2: chunk_002.mp3 finished" in output
    assert "[SUCCESS] Whisper Transcription finished | elapsed:" in output
    chunk_metrics = [
        metric for metric in logger.recorded_metrics() if metric.chunk_index is not None
    ]
    assert [metric.chunk_index for metric in chunk_metrics] == [1, 2]
    assert [metric.total_chunks for metric in chunk_metrics] == [2, 2]


def test_real_whisper_runtime_skips_empty_chunk_and_merges_successful_chunks(
    tmp_path,
) -> None:
    chunks_dir = tmp_path / "course" / "chunks"
    chunks_dir.mkdir(parents=True)
    for index in (1, 2, 3):
        (chunks_dir / f"chunk_{index:03d}.mp3").write_text("audio", encoding="utf-8")
    output_dir = tmp_path / "transcripts"
    provider = FasterWhisperProvider(
        model_factory=lambda model_size, **kwargs: PerFileTextModel(
            {
                "chunk_001.mp3": "第一段。",
                "chunk_002.mp3": "   ",
                "chunk_003.mp3": "第三段。",
            }
        )
    )
    stream = StringIO()

    result = run_local_whisper_transcription(
        LocalWhisperRuntimeRequest(chunks_dir=chunks_dir, output_dir=output_dir, merge=True),
        provider=provider,
        logger=create_runtime_logger(stream),
    )

    assert len(result.chunk_transcripts) == 2
    assert (output_dir / "chunk_001.txt").exists()
    assert not (output_dir / "chunk_002.txt").exists()
    assert (output_dir / "chunk_003.txt").exists()
    assert result.merged_transcript_path is not None
    assert result.merged_transcript_path.read_text(encoding="utf-8") == "第一段。\n\n第三段。\n"
    assert result.errors
    assert "returned empty transcript; skipped" in result.errors[0]
    assert (
        "[WARNING] Whisper Transcription | Chunk 2 / 3 returned empty transcript; skipped."
        in stream.getvalue()
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["chunk_count"] == 2
    assert len(manifest["transcript_files"]) == 2
    assert "returned empty transcript; skipped" in manifest["errors"][0]


def test_real_whisper_runtime_all_empty_chunks_produces_no_merged_transcript(
    tmp_path,
) -> None:
    chunks_dir = tmp_path / "course" / "chunks"
    chunks_dir.mkdir(parents=True)
    for index in (1, 2):
        (chunks_dir / f"chunk_{index:03d}.mp3").write_text("audio", encoding="utf-8")
    output_dir = tmp_path / "transcripts"
    provider = FasterWhisperProvider(
        model_factory=lambda model_size, **kwargs: PerFileTextModel(
            {"chunk_001.mp3": "", "chunk_002.mp3": " "}
        )
    )

    result = run_local_whisper_transcription(
        LocalWhisperRuntimeRequest(chunks_dir=chunks_dir, output_dir=output_dir, merge=True),
        provider=provider,
    )

    assert result.chunk_transcripts == ()
    assert result.merged_transcript_path is None
    assert len(result.errors) == 2
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["chunk_count"] == 0
    assert len(manifest["errors"]) == 2


def test_real_whisper_runtime_records_chunk_errors(tmp_path) -> None:
    chunks_dir = tmp_path / "course" / "chunks"
    chunks_dir.mkdir(parents=True)
    (chunks_dir / "chunk_001.mp3").write_text("audio", encoding="utf-8")
    output_dir = tmp_path / "transcripts"
    provider = FasterWhisperProvider(
        model_factory=lambda model_size, **kwargs: FakeModel(error=RuntimeError("bad audio"))
    )

    result = run_local_whisper_transcription(
        LocalWhisperRuntimeRequest(
            chunks_dir=chunks_dir,
            output_dir=output_dir,
        ),
        provider=provider,
    )

    assert result.chunk_transcripts == ()
    assert result.errors
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["chunk_count"] == 0
    assert manifest["errors"]
