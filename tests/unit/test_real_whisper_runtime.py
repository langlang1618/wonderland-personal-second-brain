import json

from ai_knowledge_pipeline.modules.transcription import FasterWhisperProvider
from scripts.run_local_whisper_transcription import (
    LocalWhisperRuntimeRequest,
    scan_chunk_files,
    run_local_whisper_transcription,
)
from tests.unit.test_faster_whisper_provider import FakeModel


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
