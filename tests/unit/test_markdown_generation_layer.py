from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactConsumerKind,
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
    ArtifactVisibility,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.cleaning.types import (
    ActionItem,
    CleanedTranscriptArtifact,
    KeyInsight,
    MarkdownBlockKind,
    MarkdownReadyBlock,
    MarkdownReadyChapter,
    MarkdownReadyTranscript,
    TranscriptCleaningStatus,
)
from ai_knowledge_pipeline.modules.markdown.contracts import (
    MarkdownGenerationConfig,
    MarkdownGenerationErrorCode,
    MarkdownGenerationRequest,
    MarkdownGenerationStatus,
    create_default_markdown_generator,
)


def cleaned_artifact(
    title: str = "Clean Lecture",
    cleaned_text: str = "Clean transcript body.",
) -> CleanedTranscriptArtifact:
    ready = MarkdownReadyTranscript(
        title=title,
        summary="A compact summary.",
        cleaned_text=cleaned_text,
        chapters=(
            MarkdownReadyChapter(
                chapter_index=0,
                title="Intro",
                summary="Opening ideas.",
                start_time=0,
                end_time=90,
                semantic_tags=("intro",),
                blocks=(
                    MarkdownReadyBlock(
                        block_index=0,
                        kind=MarkdownBlockKind.PARAGRAPH,
                        text="This is the opening paragraph.",
                    ),
                    MarkdownReadyBlock(
                        block_index=1,
                        kind=MarkdownBlockKind.BULLET_LIST,
                        text="First point\nSecond point",
                    ),
                ),
            ),
        ),
        key_insights=(
            KeyInsight(insight_index=0, text="Clean inputs improve RAG."),
        ),
        action_items=(
            ActionItem(action_index=0, text="Review generated note.", owner="me"),
        ),
        semantic_tags=("rag", "obsidian"),
    )
    snapshot = ArtifactSnapshot(
        artifact_id="cleaned_transcript_1",
        snapshot_id="cleaned_transcript_1_v1",
        kind=ArtifactKind.CLEAN_TRANSCRIPT,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/transcripts/cleaned/src_1/chunk_0000.json",
            path=Path("data/transcripts/cleaned/src_1/chunk_0000.json"),
            media_type="application/json",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id="src_1",
            input_snapshot_ids=("transcript_1_v1",),
            upstream_artifact_ids=("transcript_1",),
        ),
        metadata=ArtifactMetadata(
            title=title,
            language="en",
            tags=("ai",),
            duration_seconds=120,
            chunk_index=0,
            chunk_count=1,
        ),
    )
    return CleanedTranscriptArtifact(
        cleaned_transcript_artifact_id="cleaned_transcript_1",
        source_id="src_1",
        parent_transcript_artifact_id="transcript_1",
        chunk_index=0,
        status=TranscriptCleaningStatus.CLEANED,
        markdown_ready=ready,
        language="en",
        confidence=0.95,
        path=Path("data/transcripts/cleaned/src_1/chunk_0000.json"),
        uri="file://data/transcripts/cleaned/src_1/chunk_0000.json",
        snapshot=snapshot,
    )


def test_markdown_generator_outputs_obsidian_ready_structure() -> None:
    generator = create_default_markdown_generator()
    request = MarkdownGenerationRequest(
        cleaned_transcript=cleaned_artifact(),
        config=MarkdownGenerationConfig(markdown_dir=Path("custom-markdown")),
        run_id="run_1",
        job_id="job_1",
        task_id="task_md_1",
    )

    result = generator.generate(request)

    assert result.is_success
    assert result.status is MarkdownGenerationStatus.GENERATED
    assert result.markdown is not None
    markdown = result.markdown
    text = markdown.markdown_text
    assert text.startswith("---\n")
    assert 'title: "Clean Lecture"' in text
    assert 'tags: ["ai", "rag", "obsidian"]' in text
    assert "# Clean Lecture" in text
    assert "## Summary" in text
    assert "A compact summary." in text
    assert "## Chapters" in text
    assert "### Intro" in text
    assert "_Time: 00:00 - 01:30_" in text
    assert "This is the opening paragraph." in text
    assert "- First point" in text
    assert "## Key Insights" in text
    assert "- Clean inputs improve RAG." in text
    assert "## Action Items" in text
    assert "- [ ] Review generated note. @me" in text
    assert "## Tags" in text
    assert "#rag #obsidian" in text
    assert "## Clean Transcript" in text
    assert "Clean transcript body." in text
    assert markdown.path == Path("custom-markdown/src_1/chunk_0000_clean-lecture.md")


def test_markdown_artifact_has_lineage_and_snapshot_metadata() -> None:
    generator = create_default_markdown_generator()
    result = generator.generate(
        MarkdownGenerationRequest(cleaned_transcript=cleaned_artifact())
    )

    assert result.markdown is not None
    artifact = result.markdown
    assert artifact.snapshot.kind is ArtifactKind.MARKDOWN
    assert artifact.snapshot.lineage.input_snapshot_ids == ("cleaned_transcript_1_v1",)
    assert artifact.snapshot.lineage.upstream_artifact_ids == ("cleaned_transcript_1",)
    assert ArtifactVisibility.USER_FACING in artifact.snapshot.visibility
    assert ArtifactVisibility.RAG_INDEXABLE in artifact.snapshot.visibility
    assert ArtifactConsumerKind.OBSIDIAN in artifact.snapshot.metadata.consumer_kinds
    assert ArtifactConsumerKind.RAG in artifact.snapshot.metadata.consumer_kinds
    assert artifact.snapshot.metadata.extra["markdown_length"] == len(
        artifact.markdown_text
    )


def test_markdown_generator_can_omit_frontmatter() -> None:
    result = create_default_markdown_generator().generate(
        MarkdownGenerationRequest(
            cleaned_transcript=cleaned_artifact(),
            config=MarkdownGenerationConfig(include_frontmatter=False),
        )
    )

    assert result.markdown is not None
    assert not result.markdown.markdown_text.startswith("---")
    assert result.markdown.markdown_text.startswith("# Clean Lecture")


def test_markdown_generation_requires_title() -> None:
    result = create_default_markdown_generator().generate(
        MarkdownGenerationRequest(cleaned_transcript=cleaned_artifact(title=""))
    )

    assert not result.is_success
    assert result.issues[0].code is MarkdownGenerationErrorCode.MISSING_TITLE


def test_markdown_generation_requires_cleaned_text() -> None:
    result = create_default_markdown_generator().generate(
        MarkdownGenerationRequest(cleaned_transcript=cleaned_artifact(cleaned_text=""))
    )

    assert not result.is_success
    assert result.issues[0].code is MarkdownGenerationErrorCode.MISSING_CLEANED_TEXT
