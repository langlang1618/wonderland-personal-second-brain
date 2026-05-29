"""Default transcription orchestration."""

from __future__ import annotations

from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactConsumerKind,
    ArtifactIntegrity,
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
    ArtifactVisibility,
    IntegrityAlgorithm,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.transcription.errors import (
    TranscriptionErrorCode,
    TranscriptionIssue,
)
from ai_knowledge_pipeline.modules.transcription.interfaces import (
    Transcriber,
    TranscriptionProvider,
)
from ai_knowledge_pipeline.modules.transcription.providers import (
    UnavailableTranscriptionProvider,
)
from ai_knowledge_pipeline.modules.transcription.types import (
    ProviderTranscriptionResult,
    TranscriptArtifact,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
)


class DefaultTranscriber(Transcriber):
    """Default provider-backed transcription orchestration."""

    def __init__(self, provider: TranscriptionProvider | None = None) -> None:
        self._provider = provider or UnavailableTranscriptionProvider()

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        if request.chunk.path is None:
            issue = TranscriptionIssue(
                code=TranscriptionErrorCode.MISSING_CHUNK_PATH,
                message="Transcription requires a local chunk path.",
                field="chunk.path",
            )
            return TranscriptionResult(
                transcript=None,
                status=TranscriptionStatus.FAILED,
                issues=(issue,),
            )

        provider_result = self._provider.transcribe(request)
        if not provider_result.is_success:
            return TranscriptionResult(
                transcript=None,
                status=TranscriptionStatus.FAILED,
                issues=provider_result.issues
                or (
                    TranscriptionIssue(
                        code=TranscriptionErrorCode.INVALID_PROVIDER_RESULT,
                        message="Provider did not return transcript text.",
                        field="provider_result.text",
                    ),
                ),
            )

        transcript = self._artifact(request, provider_result)
        return TranscriptionResult(
            transcript=transcript,
            status=TranscriptionStatus.TRANSCRIBED,
            metadata={"provider": self._provider.name},
        )

    def _artifact(
        self,
        request: TranscriptionRequest,
        provider_result: ProviderTranscriptionResult,
    ) -> TranscriptArtifact:
        chunk = request.chunk
        artifact_id = f"transcript_{chunk.chunk_artifact_id}"
        snapshot_id = f"{artifact_id}_v1"
        output_path = _transcript_path(request)
        uri = output_path.as_uri() if output_path.is_absolute() else f"file://{output_path}"
        language = provider_result.language or request.config.language
        model_name = provider_result.model_name or request.config.model_name

        snapshot = ArtifactSnapshot(
            artifact_id=artifact_id,
            snapshot_id=snapshot_id,
            kind=ArtifactKind.RAW_TRANSCRIPT,
            status=ArtifactStatus.MATERIALIZED,
            location=ArtifactLocation(
                storage_class=ArtifactStorageClass.LOCAL_FILE,
                uri=uri,
                path=output_path,
                media_type="application/json",
            ),
            version=ArtifactVersion(version_id="v1", version_index=1),
            lineage=ArtifactLineage(
                source_id=chunk.source_id,
                run_id=request.run_id,
                job_id=request.job_id,
                task_id=request.task_id,
                stage_id=request.stage_id,
                input_snapshot_ids=(chunk.snapshot.snapshot_id,),
                upstream_artifact_ids=(chunk.chunk_artifact_id,),
            ),
            integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
            metadata=ArtifactMetadata(
                title=chunk.snapshot.metadata.title,
                language=language,
                tags=chunk.snapshot.metadata.tags,
                content_type="text/plain",
                text_format=request.config.transcript_format.value,
                duration_seconds=chunk.duration,
                chunk_index=chunk.chunk_index,
                chunk_count=chunk.snapshot.metadata.chunk_count,
                model_name=model_name,
                prompt_version=request.config.prompt_version,
                consumer_kinds=(
                    ArtifactConsumerKind.AI_CLEANING,
                    ArtifactConsumerKind.RAG,
                ),
                extra={
                    "parent_chunk_artifact_id": chunk.chunk_artifact_id,
                    "parent_snapshot_id": chunk.snapshot.snapshot_id,
                    "segment_count": len(provider_result.segments),
                    "confidence": provider_result.confidence,
                    **provider_result.metadata,
                },
            ),
            visibility=(ArtifactVisibility.INTERNAL, ArtifactVisibility.AI_CONTEXT),
        )

        return TranscriptArtifact(
            transcript_artifact_id=artifact_id,
            source_id=chunk.source_id,
            parent_chunk_artifact_id=chunk.chunk_artifact_id,
            chunk_index=chunk.chunk_index,
            status=TranscriptionStatus.TRANSCRIBED,
            text=provider_result.text,
            segments=provider_result.segments,
            language=language,
            confidence=provider_result.confidence,
            path=output_path,
            uri=uri,
            snapshot=snapshot,
            metadata={
                "provider": self._provider.name,
                "format": request.config.transcript_format.value,
            },
        )


def _transcript_path(request: TranscriptionRequest) -> Path:
    return (
        request.config.raw_transcripts_dir
        / request.chunk.source_id
        / f"chunk_{request.chunk.chunk_index:04d}.json"
    )


def create_default_transcriber(
    provider: TranscriptionProvider | None = None,
) -> DefaultTranscriber:
    """Create the default transcriber."""

    return DefaultTranscriber(provider=provider)


__all__ = ["DefaultTranscriber", "create_default_transcriber"]
