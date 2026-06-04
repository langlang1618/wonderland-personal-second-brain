from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.demo import (
    run_local_whisper_demo_pipeline,
)
from ai_knowledge_pipeline.modules.chunking.types import (
    MediaChunkArtifact,
    MediaChunkingStatus,
)
from ai_knowledge_pipeline.modules.transcription import (
    LocalWhisperProvider,
    TranscriptionConfig,
    TranscriptionErrorCode,
    TranscriptionProviderKind,
    TranscriptionRequest,
    TranscriptionStatus,
    create_default_transcriber,
)


def chunk_artifact() -> MediaChunkArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id="chunk_src_1_0000",
        snapshot_id="chunk_src_1_0000_v1",
        kind=ArtifactKind.CHUNK,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/chunks/src_1/chunk_0000.m4a",
            path=Path("data/chunks/src_1/chunk_0000.m4a"),
            media_type="audio/*",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(source_id="src_1"),
        metadata=ArtifactMetadata(
            title="课程01",
            language="zh",
            chunk_index=0,
            chunk_count=1,
            duration_seconds=120,
        ),
    )
    return MediaChunkArtifact(
        chunk_artifact_id="chunk_src_1_0000",
        source_id="src_1",
        parent_media_artifact_id="media_src_1",
        chunk_index=0,
        start_time=0,
        end_time=120,
        duration=120,
        status=MediaChunkingStatus.MATERIALIZED,
        path=Path("data/chunks/src_1/chunk_0000.m4a"),
        uri="file://data/chunks/src_1/chunk_0000.m4a",
        snapshot=snapshot,
    )


def request_for(path: Path) -> TranscriptionRequest:
    return TranscriptionRequest(
        chunk=chunk_artifact(),
        config=TranscriptionConfig(
            provider=TranscriptionProviderKind.LOCAL_WHISPER,
            language="zh",
            model_name="macwhisper-import",
            local_transcript_path=path,
        ),
    )


def test_local_whisper_imports_txt_transcript(tmp_path) -> None:
    transcript_path = tmp_path / "课程01.txt"
    transcript_path.write_text("这是第一节课程的转录文本。", encoding="utf-8")

    result = create_default_transcriber(provider=LocalWhisperProvider()).transcribe(
        request_for(transcript_path)
    )

    assert result.is_success
    assert result.status is TranscriptionStatus.TRANSCRIBED
    assert result.transcript is not None
    assert result.transcript.text == "这是第一节课程的转录文本。"
    assert result.transcript.language == "zh"
    assert len(result.transcript.segments) == 1
    assert result.transcript.segments[0].timestamp.start_time == 0
    assert result.transcript.segments[0].timestamp.end_time == 120
    assert result.transcript.snapshot.metadata.extra["source_format"] == "txt"


def test_local_whisper_imports_srt_with_timestamps(tmp_path) -> None:
    transcript_path = tmp_path / "课程01.srt"
    transcript_path.write_text(
        "\n".join(
            (
                "1",
                "00:00:01,000 --> 00:00:03,500",
                "欢迎来到第一课。",
                "",
                "2",
                "00:00:04,000 --> 00:00:06,250",
                "我们讨论本地优先的知识流水线。",
            )
        ),
        encoding="utf-8",
    )

    result = create_default_transcriber(provider=LocalWhisperProvider()).transcribe(
        request_for(transcript_path)
    )

    assert result.is_success
    assert result.transcript is not None
    assert result.transcript.text == (
        "欢迎来到第一课。\n我们讨论本地优先的知识流水线。"
    )
    assert len(result.transcript.segments) == 2
    assert result.transcript.segments[0].timestamp.start_time == 1
    assert result.transcript.segments[0].timestamp.end_time == 3.5
    assert result.transcript.segments[1].timestamp.start_time == 4
    assert result.transcript.segments[1].timestamp.end_time == 6.25
    assert result.transcript.snapshot.metadata.extra["source_format"] == "srt"
    assert result.transcript.snapshot.metadata.extra["segment_count"] == 2


def test_local_whisper_missing_file_returns_structured_error(tmp_path) -> None:
    result = create_default_transcriber(provider=LocalWhisperProvider()).transcribe(
        request_for(tmp_path / "missing.srt")
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptionErrorCode.MISSING_TRANSCRIPT_FILE


def test_local_whisper_rejects_unsupported_format(tmp_path) -> None:
    transcript_path = tmp_path / "课程01.md"
    transcript_path.write_text("hello", encoding="utf-8")

    result = create_default_transcriber(provider=LocalWhisperProvider()).transcribe(
        request_for(transcript_path)
    )

    assert not result.is_success
    assert (
        result.issues[0].code
        is TranscriptionErrorCode.UNSUPPORTED_TRANSCRIPT_FORMAT
    )


def test_local_whisper_demo_pipeline_writes_note_from_srt(tmp_path) -> None:
    transcript_path = tmp_path / "课程01.srt"
    transcript_path.write_text(
        "\n".join(
            (
                "1",
                "00:00:00,000 --> 00:00:02,000",
                "Local Whisper transcript import works.",
            )
        ),
        encoding="utf-8",
    )

    result = run_local_whisper_demo_pipeline(
        local_audio_path=Path("课程01.m4a"),
        local_transcript_path=transcript_path,
        temp_vault_path=tmp_path / "vault",
    )

    assert result.obsidian_note_path.exists()
    assert result.artifacts.transcript.text == "Local Whisper transcript import works."
    assert result.artifacts.transcript.snapshot.metadata.extra["source_format"] == "srt"
    markdown = result.obsidian_note_path.read_text(encoding="utf-8")
    assert "# AI整理部分" in markdown
    assert "## AI Knowledge Pipeline Demo" in markdown
    assert "## Summary" in markdown
