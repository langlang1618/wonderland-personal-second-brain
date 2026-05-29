"""Default Obsidian vault writer."""

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
from ai_knowledge_pipeline.modules.obsidian.errors import (
    ObsidianWriteErrorCode,
    ObsidianWriteIssue,
    ObsidianWriteIssueSeverity,
)
from ai_knowledge_pipeline.modules.obsidian.interfaces import (
    ObsidianPathPlanner,
    ObsidianWriter,
)
from ai_knowledge_pipeline.modules.obsidian.planner import DefaultObsidianPathPlanner
from ai_knowledge_pipeline.modules.obsidian.types import (
    ObsidianConflictStrategy,
    ObsidianNoteArtifact,
    ObsidianWriteRequest,
    ObsidianWriteResult,
    ObsidianWriteStatus,
)


class DefaultObsidianWriter(ObsidianWriter):
    """Write Markdown artifacts into an Obsidian vault."""

    def __init__(self, planner: ObsidianPathPlanner | None = None) -> None:
        self._planner = planner or DefaultObsidianPathPlanner()

    def write(self, request: ObsidianWriteRequest) -> ObsidianWriteResult:
        if request.config.vault_path is None:
            return ObsidianWriteResult(
                note=None,
                status=ObsidianWriteStatus.FAILED,
                issues=(
                    ObsidianWriteIssue(
                        code=ObsidianWriteErrorCode.MISSING_VAULT_PATH,
                        message="Obsidian vault path is required.",
                        field="config.vault_path",
                    ),
                ),
            )
        if not request.markdown.markdown_text.strip():
            return ObsidianWriteResult(
                note=None,
                status=ObsidianWriteStatus.FAILED,
                issues=(
                    ObsidianWriteIssue(
                        code=ObsidianWriteErrorCode.EMPTY_MARKDOWN,
                        message="Markdown artifact text is empty.",
                        field="markdown.markdown_text",
                    ),
                ),
            )

        try:
            target_path = self._resolve_conflict(
                self._planner.plan_path(request),
                request.config.conflict_strategy,
            )
            if target_path is None:
                skipped_path = self._planner.plan_path(request)
                return ObsidianWriteResult(
                    note=None,
                    status=ObsidianWriteStatus.SKIPPED,
                    path=skipped_path,
                    issues=(
                        ObsidianWriteIssue(
                            code=ObsidianWriteErrorCode.SKIPPED_EXISTING,
                            message="Obsidian note already exists and skip strategy is active.",
                            severity=ObsidianWriteIssueSeverity.INFO,
                            field="path",
                            details={"path": str(skipped_path)},
                        ),
                    ),
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(request.markdown.markdown_text, encoding="utf-8")
        except OSError as exc:
            return ObsidianWriteResult(
                note=None,
                status=ObsidianWriteStatus.FAILED,
                issues=(
                    ObsidianWriteIssue(
                        code=ObsidianWriteErrorCode.WRITE_FAILED,
                        message=str(exc),
                        field="path",
                    ),
                ),
            )

        note = self._artifact(request, target_path)
        return ObsidianWriteResult(
            note=note,
            status=ObsidianWriteStatus.WRITTEN,
            path=target_path,
        )

    def _resolve_conflict(
        self,
        target_path: Path,
        strategy: ObsidianConflictStrategy,
    ) -> Path | None:
        if not target_path.exists():
            return target_path
        if strategy is ObsidianConflictStrategy.OVERWRITE:
            return target_path
        if strategy is ObsidianConflictStrategy.SKIP:
            return None

        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        index = 2
        while True:
            candidate = parent / f"{stem}-v{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _artifact(
        self,
        request: ObsidianWriteRequest,
        path: Path,
    ) -> ObsidianNoteArtifact:
        markdown = request.markdown
        artifact_id = f"obsidian_{markdown.markdown_artifact_id}"
        snapshot_id = f"{artifact_id}_v1"
        uri = path.as_uri() if path.is_absolute() else f"file://{path}"

        snapshot = ArtifactSnapshot(
            artifact_id=artifact_id,
            snapshot_id=snapshot_id,
            kind=ArtifactKind.OBSIDIAN_NOTE,
            status=ArtifactStatus.MATERIALIZED,
            location=ArtifactLocation(
                storage_class=ArtifactStorageClass.LOCAL_FILE,
                uri=uri,
                path=path,
                media_type="text/markdown",
            ),
            version=ArtifactVersion(version_id="v1", version_index=1),
            lineage=ArtifactLineage(
                source_id=markdown.source_id,
                run_id=request.run_id,
                job_id=request.job_id,
                task_id=request.task_id,
                stage_id=request.stage_id,
                input_snapshot_ids=(markdown.snapshot.snapshot_id,),
                upstream_artifact_ids=(markdown.markdown_artifact_id,),
            ),
            integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
            metadata=ArtifactMetadata(
                title=markdown.snapshot.metadata.title,
                language=markdown.snapshot.metadata.language,
                tags=markdown.snapshot.metadata.tags,
                content_type="text/markdown",
                text_format="markdown",
                duration_seconds=markdown.snapshot.metadata.duration_seconds,
                chunk_index=markdown.chunk_index,
                chunk_count=markdown.snapshot.metadata.chunk_count,
                consumer_kinds=(ArtifactConsumerKind.OBSIDIAN,),
                extra={
                    "parent_markdown_artifact_id": markdown.markdown_artifact_id,
                    "parent_snapshot_id": markdown.snapshot.snapshot_id,
                    "vault_path": str(request.config.vault_path),
                    "note_path": str(path),
                },
            ),
            visibility=(ArtifactVisibility.USER_FACING,),
        )

        return ObsidianNoteArtifact(
            obsidian_note_artifact_id=artifact_id,
            source_id=markdown.source_id,
            parent_markdown_artifact_id=markdown.markdown_artifact_id,
            status=ObsidianWriteStatus.WRITTEN,
            path=path,
            uri=uri,
            snapshot=snapshot,
            metadata={"conflict_strategy": request.config.conflict_strategy.value},
        )


def create_default_obsidian_writer(
    planner: ObsidianPathPlanner | None = None,
) -> DefaultObsidianWriter:
    """Create the default Obsidian writer."""

    return DefaultObsidianWriter(planner=planner)


__all__ = ["DefaultObsidianWriter", "create_default_obsidian_writer"]
