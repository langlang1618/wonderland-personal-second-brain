"""Default Markdown generation orchestration."""

from __future__ import annotations

import re
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
from ai_knowledge_pipeline.modules.markdown.interfaces import (
    MarkdownGenerator,
    MarkdownRenderer,
)
from ai_knowledge_pipeline.modules.markdown.renderer import ObsidianMarkdownRenderer
from ai_knowledge_pipeline.modules.markdown.types import (
    MarkdownArtifact,
    MarkdownGenerationRequest,
    MarkdownGenerationResult,
    MarkdownGenerationStatus,
)


class DefaultMarkdownGenerator(MarkdownGenerator):
    """Default cleaned transcript to Markdown artifact orchestration."""

    def __init__(self, renderer: MarkdownRenderer | None = None) -> None:
        self._renderer = renderer or ObsidianMarkdownRenderer()

    def generate(self, request: MarkdownGenerationRequest) -> MarkdownGenerationResult:
        render_result = self._renderer.render(request)
        if not render_result.is_success:
            return MarkdownGenerationResult(
                markdown=None,
                status=MarkdownGenerationStatus.FAILED,
                issues=render_result.issues,
            )

        markdown = self._artifact(request, render_result.markdown_text, render_result.frontmatter)
        return MarkdownGenerationResult(
            markdown=markdown,
            status=MarkdownGenerationStatus.GENERATED,
        )

    def _artifact(
        self,
        request: MarkdownGenerationRequest,
        markdown_text: str,
        frontmatter,
    ) -> MarkdownArtifact:
        cleaned = request.cleaned_transcript
        ready = cleaned.markdown_ready
        artifact_id = f"markdown_{cleaned.cleaned_transcript_artifact_id}"
        snapshot_id = f"{artifact_id}_v1"
        path = _markdown_path(request)
        uri = path.as_uri() if path.is_absolute() else f"file://{path}"

        snapshot = ArtifactSnapshot(
            artifact_id=artifact_id,
            snapshot_id=snapshot_id,
            kind=ArtifactKind.MARKDOWN,
            status=ArtifactStatus.MATERIALIZED,
            location=ArtifactLocation(
                storage_class=ArtifactStorageClass.LOCAL_FILE,
                uri=uri,
                path=path,
                media_type="text/markdown",
            ),
            version=ArtifactVersion(version_id="v1", version_index=1),
            lineage=ArtifactLineage(
                source_id=cleaned.source_id,
                run_id=request.run_id,
                job_id=request.job_id,
                task_id=request.task_id,
                stage_id=request.stage_id,
                input_snapshot_ids=(cleaned.snapshot.snapshot_id,),
                upstream_artifact_ids=(cleaned.cleaned_transcript_artifact_id,),
            ),
            integrity=ArtifactIntegrity(algorithm=IntegrityAlgorithm.NONE),
            metadata=ArtifactMetadata(
                title=ready.title,
                language=cleaned.language,
                tags=frontmatter.get("tags", ()),
                content_type="text/markdown",
                text_format="markdown",
                duration_seconds=cleaned.snapshot.metadata.duration_seconds,
                chunk_index=cleaned.chunk_index,
                chunk_count=cleaned.snapshot.metadata.chunk_count,
                consumer_kinds=(
                    ArtifactConsumerKind.OBSIDIAN,
                    ArtifactConsumerKind.RAG,
                ),
                extra={
                    "parent_cleaned_transcript_artifact_id": (
                        cleaned.cleaned_transcript_artifact_id
                    ),
                    "parent_snapshot_id": cleaned.snapshot.snapshot_id,
                    "frontmatter_keys": tuple(frontmatter.keys()),
                    "markdown_length": len(markdown_text),
                },
            ),
            visibility=(
                ArtifactVisibility.USER_FACING,
                ArtifactVisibility.RAG_INDEXABLE,
            ),
        )

        return MarkdownArtifact(
            markdown_artifact_id=artifact_id,
            source_id=cleaned.source_id,
            parent_cleaned_transcript_artifact_id=(
                cleaned.cleaned_transcript_artifact_id
            ),
            chunk_index=cleaned.chunk_index,
            status=MarkdownGenerationStatus.GENERATED,
            markdown_text=markdown_text,
            frontmatter=frontmatter,
            path=path,
            uri=uri,
            snapshot=snapshot,
            metadata={"format": "obsidian_markdown"},
        )


def _markdown_path(request: MarkdownGenerationRequest) -> Path:
    cleaned = request.cleaned_transcript
    title_slug = _slugify(cleaned.markdown_ready.title)
    extension = request.config.file_extension
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return (
        request.config.markdown_dir
        / cleaned.source_id
        / f"chunk_{cleaned.chunk_index:04d}_{title_slug}{normalized_extension}"
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "untitled"


def create_default_markdown_generator(
    renderer: MarkdownRenderer | None = None,
) -> DefaultMarkdownGenerator:
    """Create the default Markdown generator."""

    return DefaultMarkdownGenerator(renderer=renderer)


__all__ = ["DefaultMarkdownGenerator", "create_default_markdown_generator"]
