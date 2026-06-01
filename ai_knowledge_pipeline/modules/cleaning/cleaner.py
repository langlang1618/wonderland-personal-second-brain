"""Default transcript cleaning orchestration."""

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
from ai_knowledge_pipeline.modules.cleaning.errors import (
    TranscriptCleaningErrorCode,
    TranscriptCleaningIssue,
)
from ai_knowledge_pipeline.modules.cleaning.interfaces import (
    TranscriptCleaner,
    TranscriptCleaningProvider,
)
from ai_knowledge_pipeline.modules.cleaning.providers import UnavailableCleaningProvider
from ai_knowledge_pipeline.modules.cleaning.types import (
    CleanedTranscriptArtifact,
    CleaningProviderResult,
    TranscriptCleaningRequest,
    TranscriptCleaningResult,
    TranscriptCleaningStatus,
)


class DefaultTranscriptCleaner(TranscriptCleaner):
    """Default provider-backed transcript cleaning orchestration."""

    def __init__(self, provider: TranscriptCleaningProvider | None = None) -> None:
        self._provider = provider or UnavailableCleaningProvider()

    def clean(self, request: TranscriptCleaningRequest) -> TranscriptCleaningResult:
        if not request.transcript.text.strip():
            issue = TranscriptCleaningIssue(
                code=TranscriptCleaningErrorCode.MISSING_TRANSCRIPT_TEXT,
                message="Transcript cleaning requires raw transcript text.",
                field="transcript.text",
            )
            return TranscriptCleaningResult(
                cleaned_transcript=None,
                status=TranscriptCleaningStatus.FAILED,
                issues=(issue,),
            )

        provider_result = self._provider.clean(request)
        if not provider_result.is_success:
            return TranscriptCleaningResult(
                cleaned_transcript=None,
                status=TranscriptCleaningStatus.FAILED,
                issues=provider_result.issues
                or (
                    TranscriptCleaningIssue(
                        code=TranscriptCleaningErrorCode.INVALID_PROVIDER_RESULT,
                        message="Provider did not return markdown-ready content.",
                        field="provider_result.markdown_ready",
                    ),
                ),
            )

        cleaned_transcript = self._artifact(request, provider_result)
        return TranscriptCleaningResult(
            cleaned_transcript=cleaned_transcript,
            status=TranscriptCleaningStatus.CLEANED,
            metadata={"provider": self._provider.name},
        )

    def _artifact(
        self,
        request: TranscriptCleaningRequest,
        provider_result: CleaningProviderResult,
    ) -> CleanedTranscriptArtifact:
        transcript = request.transcript
        markdown_ready = provider_result.markdown_ready
        if markdown_ready is None:
            raise ValueError("provider_result.markdown_ready is required")

        artifact_id = f"cleaned_{transcript.transcript_artifact_id}"
        snapshot_id = f"{artifact_id}_v1"
        output_path = _cleaned_transcript_path(request)
        uri = output_path.as_uri() if output_path.is_absolute() else f"file://{output_path}"
        language = provider_result.language or request.config.language or transcript.language
        model_name = provider_result.model_name or request.config.model_name
        prompt_version = provider_result.prompt_version or request.config.prompt_version

        snapshot = ArtifactSnapshot(
            artifact_id=artifact_id,
            snapshot_id=snapshot_id,
            kind=ArtifactKind.CLEAN_TRANSCRIPT,
            status=ArtifactStatus.MATERIALIZED,
            location=ArtifactLocation(
                storage_class=ArtifactStorageClass.LOCAL_FILE,
                uri=uri,
                path=output_path,
                media_type="application/json",
            ),
            version=ArtifactVersion(version_id="v1", version_index=1),
            lineage=ArtifactLineage(
                source_id=transcript.source_id,
                run_id=request.run_id,
                job_id=request.job_id,
                task_id=request.task_id,
                stage_id=request.stage_id,
                input_snapshot_ids=(transcript.snapshot.snapshot_id,),
                upstream_artifact_ids=(transcript.transcript_artifact_id,),
            ),
            integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
            metadata=ArtifactMetadata(
                title=markdown_ready.title,
                language=language,
                tags=(*transcript.snapshot.metadata.tags, *markdown_ready.semantic_tags),
                content_type="text/markdown",
                text_format="markdown_ready_json",
                duration_seconds=transcript.snapshot.metadata.duration_seconds,
                chunk_index=transcript.chunk_index,
                chunk_count=transcript.snapshot.metadata.chunk_count,
                model_name=model_name,
                prompt_version=prompt_version,
                consumer_kinds=(
                    ArtifactConsumerKind.MARKDOWN_RENDERING,
                    ArtifactConsumerKind.RAG,
                    ArtifactConsumerKind.AGENT_MEMORY,
                ),
                extra={
                    "parent_transcript_artifact_id": transcript.transcript_artifact_id,
                    "parent_snapshot_id": transcript.snapshot.snapshot_id,
                    "chapter_count": len(markdown_ready.chapters),
                    "key_insight_count": len(markdown_ready.key_insights),
                    "action_item_count": len(markdown_ready.action_items),
                    "agent_memory_candidate_count": len(
                        markdown_ready.agent_memory_candidates
                    ),
                    "confidence": provider_result.confidence,
                    **provider_result.metadata,
                },
            ),
            visibility=(
                ArtifactVisibility.INTERNAL,
                ArtifactVisibility.AI_CONTEXT,
                ArtifactVisibility.RAG_INDEXABLE,
            ),
        )

        return CleanedTranscriptArtifact(
            cleaned_transcript_artifact_id=artifact_id,
            source_id=transcript.source_id,
            parent_transcript_artifact_id=transcript.transcript_artifact_id,
            chunk_index=transcript.chunk_index,
            status=TranscriptCleaningStatus.CLEANED,
            markdown_ready=markdown_ready,
            language=language,
            confidence=provider_result.confidence,
            path=output_path,
            uri=uri,
            snapshot=snapshot,
            metadata={
                "provider": self._provider.name,
                "prompt_version": prompt_version,
            },
            raw_transcript=transcript.text,
        )


def _cleaned_transcript_path(request: TranscriptCleaningRequest) -> Path:
    return (
        request.config.cleaned_transcripts_dir
        / request.transcript.source_id
        / f"chunk_{request.transcript.chunk_index:04d}.json"
    )


def create_default_transcript_cleaner(
    provider: TranscriptCleaningProvider | None = None,
) -> DefaultTranscriptCleaner:
    """Create the default transcript cleaner."""

    return DefaultTranscriptCleaner(provider=provider)


__all__ = ["DefaultTranscriptCleaner", "create_default_transcript_cleaner"]
