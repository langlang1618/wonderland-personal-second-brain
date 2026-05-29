"""Default media chunking orchestration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
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
from ai_knowledge_pipeline.modules.chunking.adapters import DefaultFfmpegCommandBuilder
from ai_knowledge_pipeline.modules.chunking.errors import (
    MediaChunkingErrorCode,
    MediaChunkingIssue,
)
from ai_knowledge_pipeline.modules.chunking.interfaces import (
    FfmpegCommandBuilder,
    MediaChunker,
    MediaChunkingAdapter,
    MediaChunkPlanner,
)
from ai_knowledge_pipeline.modules.chunking.planner import (
    DefaultMediaChunkPlanner,
    MediaChunkPlanningError,
    chunk_output_path,
)
from ai_knowledge_pipeline.modules.chunking.types import (
    MediaChunkArtifact,
    MediaChunkingMode,
    MediaChunkingRequest,
    MediaChunkingResult,
    MediaChunkingStatus,
    MediaChunkPlan,
    TimelineSegment,
)


class DefaultMediaChunker(MediaChunker):
    """Default LocalMediaArtifact to chunk artifact orchestration."""

    def __init__(
        self,
        planner: MediaChunkPlanner | None = None,
        adapter: MediaChunkingAdapter | None = None,
        command_builder: FfmpegCommandBuilder | None = None,
    ) -> None:
        self._planner = planner or DefaultMediaChunkPlanner()
        self._adapter = adapter
        self._command_builder = command_builder or DefaultFfmpegCommandBuilder()

    def chunk(self, request: MediaChunkingRequest) -> MediaChunkingResult:
        try:
            plan = self._planner.plan(request)
        except MediaChunkPlanningError as exc:
            return MediaChunkingResult(
                chunks=(),
                plan=None,
                status=MediaChunkingStatus.FAILED,
                issues=(exc.issue,),
            )

        commands = self._command_builder.build(request, plan)
        plan = replace(plan, commands=commands)

        if request.config.mode is MediaChunkingMode.DRY_RUN:
            chunks = self._artifacts(
                request,
                plan,
                MediaChunkingStatus.PLANNED,
                output_paths=tuple(
                    chunk_output_path(
                        plan.chunks_dir,
                        plan.source_id,
                        segment.chunk_index,
                        request.config.output_extension,
                    )
                    for segment in plan.segments
                ),
            )
            return MediaChunkingResult(
                chunks=chunks,
                plan=plan,
                status=MediaChunkingStatus.PLANNED,
            )

        if self._adapter is None:
            issue = MediaChunkingIssue(
                code=MediaChunkingErrorCode.ADAPTER_REQUIRED,
                message="Media chunk materialization requires an ffmpeg adapter.",
                field="adapter",
            )
            return MediaChunkingResult(
                chunks=(),
                plan=plan,
                status=MediaChunkingStatus.FAILED,
                issues=(issue,),
            )

        adapter_result = self._adapter.chunk(request, plan)
        if not adapter_result.is_success:
            return MediaChunkingResult(
                chunks=(),
                plan=plan,
                status=MediaChunkingStatus.FAILED,
                issues=adapter_result.issues,
            )

        chunks = self._artifacts(
            request,
            plan,
            MediaChunkingStatus.MATERIALIZED,
            output_paths=adapter_result.output_paths,
            metadata=adapter_result.metadata,
        )
        return MediaChunkingResult(
            chunks=chunks,
            plan=plan,
            status=MediaChunkingStatus.MATERIALIZED,
            metadata={"adapter_name": self._adapter.name},
        )

    def _artifacts(
        self,
        request: MediaChunkingRequest,
        plan: MediaChunkPlan,
        status: MediaChunkingStatus,
        output_paths: tuple[Path, ...],
        metadata=None,
    ) -> tuple[MediaChunkArtifact, ...]:
        metadata = metadata or {}
        return tuple(
            self._artifact(
                request=request,
                plan=plan,
                segment=segment,
                status=status,
                path=output_paths[segment.chunk_index],
                metadata=metadata,
            )
            for segment in plan.segments
        )

    def _artifact(
        self,
        request: MediaChunkingRequest,
        plan: MediaChunkPlan,
        segment: TimelineSegment,
        status: MediaChunkingStatus,
        path: Path,
        metadata,
    ) -> MediaChunkArtifact:
        source_id = request.media.source_id
        artifact_id = f"chunk_{source_id}_{segment.chunk_index:04d}"
        snapshot_id = f"{artifact_id}_v1"
        uri = path.as_uri() if path.is_absolute() else f"file://{path}"
        chunk_count = len(plan.segments)

        snapshot = ArtifactSnapshot(
            artifact_id=artifact_id,
            snapshot_id=snapshot_id,
            kind=ArtifactKind.CHUNK,
            status=(
                ArtifactStatus.MATERIALIZED
                if status is MediaChunkingStatus.MATERIALIZED
                else ArtifactStatus.DECLARED
            ),
            location=ArtifactLocation(
                storage_class=ArtifactStorageClass.LOCAL_FILE,
                uri=uri,
                path=path,
                media_type=request.media.snapshot.location.media_type,
            ),
            version=ArtifactVersion(version_id="v1", version_index=1),
            lineage=ArtifactLineage(
                source_id=source_id,
                run_id=request.run_id,
                job_id=request.job_id,
                task_id=request.task_id,
                stage_id=request.stage_id,
                input_snapshot_ids=(request.media.snapshot.snapshot_id,),
                upstream_artifact_ids=(request.media.media_artifact_id,),
            ),
            integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
            metadata=ArtifactMetadata(
                title=request.media.snapshot.metadata.title,
                language=request.media.snapshot.metadata.language,
                tags=request.media.snapshot.metadata.tags,
                content_type=request.media.snapshot.metadata.content_type,
                duration_seconds=segment.duration,
                chunk_index=segment.chunk_index,
                chunk_count=chunk_count,
                extra={
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "duration": segment.duration,
                    "parent_media_artifact_id": request.media.media_artifact_id,
                    "parent_snapshot_id": request.media.snapshot.snapshot_id,
                    **metadata,
                },
            ),
            visibility=(ArtifactVisibility.INTERNAL,),
        )

        return MediaChunkArtifact(
            chunk_artifact_id=artifact_id,
            source_id=source_id,
            parent_media_artifact_id=request.media.media_artifact_id,
            chunk_index=segment.chunk_index,
            start_time=segment.start_time,
            end_time=segment.end_time,
            duration=segment.duration,
            status=status,
            path=path,
            uri=uri,
            snapshot=snapshot,
            metadata={
                "parent_snapshot_id": request.media.snapshot.snapshot_id,
                "mode": request.config.mode.value,
            },
        )


def create_default_media_chunker(
    adapter: MediaChunkingAdapter | None = None,
) -> DefaultMediaChunker:
    """Create the default media chunker."""

    return DefaultMediaChunker(adapter=adapter)


__all__ = ["DefaultMediaChunker", "create_default_media_chunker"]
