from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactLocation,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.transcription import (
    ChunkTranscriptArtifact,
    TranscriptArtifact,
    TranscriptMerger,
    TranscriptionStatus,
)


def transcript(chunk_index: int, text: str) -> TranscriptArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id=f"transcript_{chunk_index}",
        snapshot_id=f"transcript_{chunk_index}_v1",
        kind=ArtifactKind.RAW_TRANSCRIPT,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri=f"file://chunk_{chunk_index}.json",
            path=Path(f"chunk_{chunk_index}.json"),
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
    )
    return TranscriptArtifact(
        transcript_artifact_id=f"transcript_{chunk_index}",
        source_id="course",
        parent_chunk_artifact_id=f"chunk_{chunk_index}",
        chunk_index=chunk_index,
        status=TranscriptionStatus.TRANSCRIBED,
        text=text,
        segments=(),
        language="zh",
        confidence=None,
        path=Path(f"chunk_{chunk_index}.json"),
        uri=f"file://chunk_{chunk_index}.json",
        snapshot=snapshot,
    )


def test_transcript_merger_orders_by_chunk_index(tmp_path) -> None:
    artifacts = (
        ChunkTranscriptArtifact(transcript=transcript(2, "第三段"), text_path=tmp_path / "3.txt"),
        ChunkTranscriptArtifact(transcript=transcript(0, "第一段"), text_path=tmp_path / "1.txt"),
        ChunkTranscriptArtifact(transcript=transcript(1, "第二段"), text_path=tmp_path / "2.txt"),
    )
    output_path = tmp_path / "merged_transcript.txt"

    result = TranscriptMerger().merge(artifacts, output_path)

    assert result.text == "第一段\n\n第二段\n\n第三段"
    assert result.path == output_path
    assert result.chunk_count == 3
    assert output_path.read_text(encoding="utf-8") == "第一段\n\n第二段\n\n第三段\n"
