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
from ai_knowledge_pipeline.modules.chunking.types import (
    MediaChunkArtifact,
    MediaChunkingStatus,
)
from ai_knowledge_pipeline.modules.transcription.contracts import (
    ProviderTranscriptionResult,
    TranscriptSegment,
    TranscriptTimestamp,
    TranscriptionConfig,
    TranscriptionErrorCode,
    TranscriptionIssue,
    TranscriptionProviderKind,
    TranscriptionRequest,
    TranscriptionStatus,
    create_default_transcriber,
)


def chunk_artifact(path: Path | None = Path("data/chunks/src_1/chunk_0000.m4a")):
    snapshot = ArtifactSnapshot(
        artifact_id="chunk_src_1_0000",
        snapshot_id="chunk_src_1_0000_v1",
        kind=ArtifactKind.CHUNK,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/chunks/src_1/chunk_0000.m4a",
            path=path,
            media_type="audio/*",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id="src_1",
            input_snapshot_ids=("media_src_1_v1",),
            upstream_artifact_ids=("media_src_1",),
        ),
        metadata=ArtifactMetadata(
            title="Lecture",
            language="en",
            tags=("ai",),
            duration_seconds=120,
            chunk_index=0,
            chunk_count=2,
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
        path=path,
        uri="file://data/chunks/src_1/chunk_0000.m4a",
        snapshot=snapshot,
    )


class MockProvider:
    name = "mock-whisper"

    def transcribe(self, request):
        return ProviderTranscriptionResult(
            text="Hello world.",
            language="en",
            confidence=0.91,
            model_name="mock-large-v3",
            segments=(
                TranscriptSegment(
                    segment_index=0,
                    timestamp=TranscriptTimestamp(start_time=0.0, end_time=2.5),
                    text="Hello world.",
                    confidence=0.91,
                ),
            ),
            metadata={"provider_request_id": "req_1"},
        )


class FailingProvider:
    name = "failing-provider"

    def transcribe(self, request):
        return ProviderTranscriptionResult(
            text="",
            issues=(
                TranscriptionIssue(
                    code=TranscriptionErrorCode.PROVIDER_FAILED,
                    message="Provider failed.",
                    field="provider",
                ),
            ),
        )


def test_transcriber_generates_transcript_artifact_with_segments_and_lineage() -> None:
    transcriber = create_default_transcriber(provider=MockProvider())
    request = TranscriptionRequest(
        chunk=chunk_artifact(),
        config=TranscriptionConfig(
            raw_transcripts_dir=Path("custom-transcripts"),
            provider=TranscriptionProviderKind.FASTER_WHISPER,
            prompt_version="transcribe-v1",
        ),
        run_id="run_1",
        job_id="job_1",
        task_id="task_transcribe_1",
    )

    result = transcriber.transcribe(request)

    assert result.is_success
    assert result.status is TranscriptionStatus.TRANSCRIBED
    assert result.transcript is not None
    transcript = result.transcript
    assert transcript.text == "Hello world."
    assert transcript.language == "en"
    assert transcript.confidence == 0.91
    assert transcript.segments[0].timestamp.start_time == 0
    assert transcript.segments[0].timestamp.end_time == 2.5
    assert transcript.path == Path("custom-transcripts/src_1/chunk_0000.json")
    assert transcript.snapshot.kind is ArtifactKind.RAW_TRANSCRIPT
    assert transcript.snapshot.lineage.input_snapshot_ids == ("chunk_src_1_0000_v1",)
    assert transcript.snapshot.lineage.upstream_artifact_ids == ("chunk_src_1_0000",)
    assert transcript.snapshot.metadata.chunk_index == 0
    assert transcript.snapshot.metadata.chunk_count == 2
    assert transcript.snapshot.metadata.extra["segment_count"] == 1
    assert transcript.snapshot.metadata.extra["provider_request_id"] == "req_1"


def test_default_transcriber_requires_provider() -> None:
    result = create_default_transcriber().transcribe(
        TranscriptionRequest(chunk=chunk_artifact())
    )

    assert not result.is_success
    assert result.status is TranscriptionStatus.FAILED
    assert result.issues[0].code is TranscriptionErrorCode.PROVIDER_REQUIRED


def test_transcriber_requires_chunk_path() -> None:
    result = create_default_transcriber(provider=MockProvider()).transcribe(
        TranscriptionRequest(chunk=chunk_artifact(path=None))
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptionErrorCode.MISSING_CHUNK_PATH


def test_provider_failure_is_structured() -> None:
    result = create_default_transcriber(provider=FailingProvider()).transcribe(
        TranscriptionRequest(chunk=chunk_artifact())
    )

    assert not result.is_success
    assert result.issues[0].code is TranscriptionErrorCode.PROVIDER_FAILED


def test_timestamp_duration_is_derived() -> None:
    timestamp = TranscriptTimestamp(start_time=10.5, end_time=14.0)

    assert timestamp.duration == 3.5
