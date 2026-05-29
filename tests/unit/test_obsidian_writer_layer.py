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
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.modules.markdown.types import (
    MarkdownArtifact,
    MarkdownGenerationStatus,
)
from ai_knowledge_pipeline.modules.obsidian.contracts import (
    ObsidianConflictStrategy,
    ObsidianWriteErrorCode,
    ObsidianWriteRequest,
    ObsidianWriteStatus,
    ObsidianWriterConfig,
    create_default_obsidian_writer,
)


def markdown_artifact(
    title: str = "Clean Lecture",
    tags: tuple[str, ...] = ("ai", "rag"),
    text: str = "# Clean Lecture\n\nBody.\n",
) -> MarkdownArtifact:
    snapshot = ArtifactSnapshot(
        artifact_id="markdown_cleaned_1",
        snapshot_id="markdown_cleaned_1_v1",
        kind=ArtifactKind.MARKDOWN,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/markdown/src_1/clean.md",
            path=Path("data/markdown/src_1/clean.md"),
            media_type="text/markdown",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id="src_1",
            input_snapshot_ids=("cleaned_1_v1",),
            upstream_artifact_ids=("cleaned_1",),
        ),
        metadata=ArtifactMetadata(
            title=title,
            language="en",
            tags=tags,
            chunk_index=0,
            chunk_count=1,
            consumer_kinds=(ArtifactConsumerKind.OBSIDIAN,),
        ),
    )
    return MarkdownArtifact(
        markdown_artifact_id="markdown_cleaned_1",
        source_id="src_1",
        parent_cleaned_transcript_artifact_id="cleaned_1",
        chunk_index=0,
        status=MarkdownGenerationStatus.GENERATED,
        markdown_text=text,
        frontmatter={"title": title, "tags": tags},
        path=Path("data/markdown/src_1/clean.md"),
        uri="file://data/markdown/src_1/clean.md",
        snapshot=snapshot,
    )


def test_writes_markdown_into_categorized_vault_path(tmp_path) -> None:
    writer = create_default_obsidian_writer()
    request = ObsidianWriteRequest(
        markdown=markdown_artifact(),
        config=ObsidianWriterConfig(vault_path=tmp_path),
        run_id="run_1",
        job_id="job_1",
        task_id="task_obsidian_1",
    )

    result = writer.write(request)

    expected = tmp_path / "AI Knowledge Pipeline" / "ai" / "clean-lecture.md"
    assert result.is_success
    assert result.status is ObsidianWriteStatus.WRITTEN
    assert result.path == expected
    assert expected.read_text(encoding="utf-8") == "# Clean Lecture\n\nBody.\n"
    assert result.note is not None
    assert result.note.snapshot.kind is ArtifactKind.OBSIDIAN_NOTE
    assert result.note.snapshot.lineage.input_snapshot_ids == ("markdown_cleaned_1_v1",)
    assert result.note.snapshot.lineage.upstream_artifact_ids == ("markdown_cleaned_1",)
    assert result.note.snapshot.metadata.extra["note_path"] == str(expected)


def test_overwrite_strategy_replaces_existing_note(tmp_path) -> None:
    writer = create_default_obsidian_writer()
    config = ObsidianWriterConfig(
        vault_path=tmp_path,
        conflict_strategy=ObsidianConflictStrategy.OVERWRITE,
    )
    target = tmp_path / "AI Knowledge Pipeline" / "ai" / "clean-lecture.md"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")

    result = writer.write(
        ObsidianWriteRequest(markdown=markdown_artifact(text="new"), config=config)
    )

    assert result.is_success
    assert target.read_text(encoding="utf-8") == "new"


def test_skip_strategy_does_not_modify_existing_note(tmp_path) -> None:
    writer = create_default_obsidian_writer()
    config = ObsidianWriterConfig(
        vault_path=tmp_path,
        conflict_strategy=ObsidianConflictStrategy.SKIP,
    )
    target = tmp_path / "AI Knowledge Pipeline" / "ai" / "clean-lecture.md"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")

    result = writer.write(
        ObsidianWriteRequest(markdown=markdown_artifact(text="new"), config=config)
    )

    assert not result.is_success
    assert result.status is ObsidianWriteStatus.SKIPPED
    assert result.issues[0].code is ObsidianWriteErrorCode.SKIPPED_EXISTING
    assert target.read_text(encoding="utf-8") == "old"


def test_versioned_strategy_writes_next_available_version(tmp_path) -> None:
    writer = create_default_obsidian_writer()
    config = ObsidianWriterConfig(
        vault_path=tmp_path,
        conflict_strategy=ObsidianConflictStrategy.VERSIONED,
    )
    target = tmp_path / "AI Knowledge Pipeline" / "ai" / "clean-lecture.md"
    target_v2 = tmp_path / "AI Knowledge Pipeline" / "ai" / "clean-lecture-v2.md"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")
    target_v2.write_text("older", encoding="utf-8")

    result = writer.write(
        ObsidianWriteRequest(markdown=markdown_artifact(text="new"), config=config)
    )

    expected = tmp_path / "AI Knowledge Pipeline" / "ai" / "clean-lecture-v3.md"
    assert result.is_success
    assert result.path == expected
    assert expected.read_text(encoding="utf-8") == "new"


def test_missing_vault_path_returns_structured_error() -> None:
    result = create_default_obsidian_writer().write(
        ObsidianWriteRequest(markdown=markdown_artifact())
    )

    assert not result.is_success
    assert result.status is ObsidianWriteStatus.FAILED
    assert result.issues[0].code is ObsidianWriteErrorCode.MISSING_VAULT_PATH


def test_empty_markdown_returns_structured_error(tmp_path) -> None:
    result = create_default_obsidian_writer().write(
        ObsidianWriteRequest(
            markdown=markdown_artifact(text=""),
            config=ObsidianWriterConfig(vault_path=tmp_path),
        )
    )

    assert not result.is_success
    assert result.issues[0].code is ObsidianWriteErrorCode.EMPTY_MARKDOWN


def test_uncategorized_path_when_no_tags(tmp_path) -> None:
    result = create_default_obsidian_writer().write(
        ObsidianWriteRequest(
            markdown=markdown_artifact(tags=()),
            config=ObsidianWriterConfig(vault_path=tmp_path),
        )
    )

    expected = (
        tmp_path
        / "AI Knowledge Pipeline"
        / "uncategorized"
        / "clean-lecture.md"
    )
    assert result.is_success
    assert result.path == expected
    assert expected.exists()
