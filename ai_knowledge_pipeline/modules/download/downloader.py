"""Default media download orchestration."""

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
from ai_knowledge_pipeline.core.source import MediaKind, SourceAccess, SourceKind
from ai_knowledge_pipeline.modules.download.adapters import DefaultYtDlpCommandBuilder
from ai_knowledge_pipeline.modules.download.errors import (
    MediaDownloadErrorCode,
    MediaDownloadIssue,
)
from ai_knowledge_pipeline.modules.download.interfaces import (
    MediaDownloadAdapter,
    MediaDownloader,
    MediaStoragePlanner,
    YtDlpCommandBuilder,
)
from ai_knowledge_pipeline.modules.download.storage import DefaultMediaStoragePlanner
from ai_knowledge_pipeline.modules.download.types import (
    LocalMediaArtifact,
    MediaDownloadConfig,
    MediaDownloadMode,
    MediaDownloadPlan,
    MediaDownloadRequest,
    MediaDownloadResult,
    MediaDownloadStatus,
)


class DefaultMediaDownloader(MediaDownloader):
    """Default SourceData to LocalMediaArtifact orchestration."""

    def __init__(
        self,
        storage_planner: MediaStoragePlanner | None = None,
        remote_adapter: MediaDownloadAdapter | None = None,
        ytdlp_command_builder: YtDlpCommandBuilder | None = None,
    ) -> None:
        self._storage_planner = storage_planner or DefaultMediaStoragePlanner()
        self._remote_adapter = remote_adapter
        self._command_builder = ytdlp_command_builder or DefaultYtDlpCommandBuilder()

    def download(self, request: MediaDownloadRequest) -> MediaDownloadResult:
        plan = self._storage_planner.plan(request)
        if request.source.kind in {SourceKind.YOUTUBE, SourceKind.M3U8}:
            plan = replace(
                plan,
                command=self._command_builder.build(
                    request.source,
                    plan,
                    request.config,
                ),
            )

        if request.source.location.access is SourceAccess.LOCAL:
            return self._local_result(request, plan)

        if request.config.mode in {
            MediaDownloadMode.DRY_RUN,
            MediaDownloadMode.METADATA_ONLY,
        }:
            status = (
                MediaDownloadStatus.PLANNED
                if request.config.mode is MediaDownloadMode.DRY_RUN
                else MediaDownloadStatus.METADATA_ONLY
            )
            artifact = self._artifact(request, plan, status, path=plan.target_path)
            return MediaDownloadResult(artifact=artifact, plan=plan, status=status)

        if self._remote_adapter is None:
            issue = MediaDownloadIssue(
                code=MediaDownloadErrorCode.ADAPTER_REQUIRED,
                message="Remote media materialization requires a download adapter.",
                field="remote_adapter",
                details={"adapter_name": plan.adapter_name},
            )
            return MediaDownloadResult(
                artifact=None,
                plan=plan,
                status=MediaDownloadStatus.FAILED,
                issues=(issue,),
            )

        adapter_result = self._remote_adapter.download(request, plan)
        if not adapter_result.is_success:
            return MediaDownloadResult(
                artifact=None,
                plan=plan,
                status=MediaDownloadStatus.FAILED,
                issues=adapter_result.issues,
            )

        artifact = self._artifact(
            request,
            plan,
            MediaDownloadStatus.DOWNLOADED,
            path=adapter_result.path,
            metadata=adapter_result.metadata,
        )
        return MediaDownloadResult(
            artifact=artifact,
            plan=plan,
            status=MediaDownloadStatus.DOWNLOADED,
            metadata={"adapter_name": self._remote_adapter.name},
        )

    def _local_result(
        self,
        request: MediaDownloadRequest,
        plan: MediaDownloadPlan,
    ) -> MediaDownloadResult:
        status = (
            MediaDownloadStatus.PLANNED
            if request.config.mode is MediaDownloadMode.DRY_RUN
            else MediaDownloadStatus.LOCAL_REFERENCE
        )
        artifact = self._artifact(request, plan, status, path=plan.target_path)
        return MediaDownloadResult(artifact=artifact, plan=plan, status=status)

    def _artifact(
        self,
        request: MediaDownloadRequest,
        plan: MediaDownloadPlan,
        status: MediaDownloadStatus,
        path: Path | None,
        metadata=None,
    ) -> LocalMediaArtifact:
        metadata = metadata or {}
        source = request.source
        artifact_id = f"media_{source.source_id}"
        snapshot_id = f"{artifact_id}_v1"
        location_path = path
        uri = location_path.as_uri() if location_path and location_path.is_absolute() else (
            f"file://{location_path}" if location_path else f"planned://{source.source_id}"
        )

        snapshot = ArtifactSnapshot(
            artifact_id=artifact_id,
            snapshot_id=snapshot_id,
            kind=ArtifactKind.MEDIA,
            status=self._artifact_status(status),
            location=ArtifactLocation(
                storage_class=ArtifactStorageClass.LOCAL_FILE,
                uri=uri,
                path=location_path,
                media_type=self._media_type(source.media_kind),
            ),
            version=ArtifactVersion(version_id="v1", version_index=1),
            lineage=ArtifactLineage(
                source_id=source.source_id,
                run_id=request.run_id,
                job_id=request.job_id,
                task_id=request.task_id,
                stage_id=request.stage_id,
            ),
            integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
            metadata=ArtifactMetadata(
                title=source.metadata.title,
                language=source.metadata.language,
                tags=source.metadata.tags,
                content_type=self._media_type(source.media_kind),
                extra={
                    "download_status": status.value,
                    "source_kind": source.kind.value,
                    **metadata,
                },
            ),
            visibility=(ArtifactVisibility.INTERNAL,),
        )
        return LocalMediaArtifact(
            media_artifact_id=artifact_id,
            source_id=source.source_id,
            status=status,
            path=location_path,
            uri=uri,
            snapshot=snapshot,
            metadata={
                "mode": request.config.mode.value,
                "adapter_name": plan.adapter_name,
            },
        )

    def _artifact_status(self, status: MediaDownloadStatus) -> ArtifactStatus:
        if status is MediaDownloadStatus.DOWNLOADED:
            return ArtifactStatus.MATERIALIZED
        if status is MediaDownloadStatus.LOCAL_REFERENCE:
            return ArtifactStatus.REGISTERED
        return ArtifactStatus.DECLARED

    def _media_type(self, media_kind: MediaKind) -> str:
        if media_kind is MediaKind.AUDIO:
            return "audio/*"
        return "video/*"


def create_default_media_downloader(
    remote_adapter: MediaDownloadAdapter | None = None,
    config: MediaDownloadConfig | None = None,
) -> DefaultMediaDownloader:
    """Create the default media downloader.

    The config argument is accepted for factory symmetry with later dependency
    injection, but per-request config remains authoritative.
    """

    _ = config
    return DefaultMediaDownloader(remote_adapter=remote_adapter)


__all__ = ["DefaultMediaDownloader", "create_default_media_downloader"]
