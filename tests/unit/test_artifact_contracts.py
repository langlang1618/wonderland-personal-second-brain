from pathlib import Path

from ai_knowledge_pipeline.core.artifact import (
    ArtifactConsumerKind,
    ArtifactIntegrity,
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactRegistryRecord,
    ArtifactRelationType,
    ArtifactRelationship,
    ArtifactRelationshipGraph,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
    ArtifactVisibility,
    IntegrityAlgorithm,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind


def test_artifact_snapshot_models_immutable_versioned_output() -> None:
    snapshot = ArtifactSnapshot(
        artifact_id="clean_transcript_src_1",
        snapshot_id="clean_transcript_src_1_v2",
        kind=ArtifactKind.CLEAN_TRANSCRIPT,
        status=ArtifactStatus.REGISTERED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/transcripts/cleaned/src_1.v2.md",
            path=Path("data/transcripts/cleaned/src_1.v2.md"),
            media_type="text/markdown",
        ),
        version=ArtifactVersion(
            version_id="v2",
            version_index=2,
            parent_version_id="v1",
            reason="AI cleaning re-run",
        ),
        lineage=ArtifactLineage(
            source_id="src_1",
            run_id="run_1",
            task_id="task_cleaning_1",
            stage_id="cleaning",
            input_snapshot_ids=("raw_transcript_src_1_v1",),
        ),
        integrity=ArtifactIntegrity(
            algorithm=IntegrityAlgorithm.SHA256,
            digest="abc123",
            size_bytes=1024,
            verified=True,
        ),
        metadata=ArtifactMetadata(
            language="en",
            prompt_version="cleaning-v2",
            consumer_kinds=(
                ArtifactConsumerKind.MARKDOWN_RENDERING,
                ArtifactConsumerKind.RAG,
            ),
        ),
        visibility=(ArtifactVisibility.AI_CONTEXT, ArtifactVisibility.RAG_INDEXABLE),
    )

    assert snapshot.version.parent_version_id == "v1"
    assert snapshot.lineage.input_snapshot_ids == ("raw_transcript_src_1_v1",)
    assert ArtifactConsumerKind.RAG in snapshot.metadata.consumer_kinds


def test_artifact_relationship_graph_links_versions_and_derivations() -> None:
    relationship = ArtifactRelationship(
        relation_id="rel_1",
        relation_type=ArtifactRelationType.DERIVED_FROM,
        from_snapshot_id="clean_transcript_src_1_v2",
        to_snapshot_id="markdown_src_1_v1",
    )
    graph = ArtifactRelationshipGraph(
        graph_id="graph_run_1",
        relationships=(relationship,),
    )

    assert graph.relationships[0].relation_type is ArtifactRelationType.DERIVED_FROM
    assert graph.relationships[0].from_snapshot_id == "clean_transcript_src_1_v2"


def test_registry_record_wraps_snapshot_without_mutating_it() -> None:
    snapshot = ArtifactSnapshot(
        artifact_id="markdown_src_1",
        snapshot_id="markdown_src_1_v1",
        kind=ArtifactKind.MARKDOWN,
        status=ArtifactStatus.VERIFIED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri="file://data/markdown/src_1.md",
            path=Path("data/markdown/src_1.md"),
            media_type="text/markdown",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
    )
    record = ArtifactRegistryRecord(snapshot=snapshot)

    assert record.snapshot.status is ArtifactStatus.VERIFIED
    assert record.manifest_version == "v1"
