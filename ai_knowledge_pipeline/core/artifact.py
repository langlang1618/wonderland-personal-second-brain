"""Artifact storage contracts.

This module defines immutable artifact snapshots, lineage, integrity, and
registry boundaries for the pipeline. It intentionally contains no downloader,
file IO, database code, or storage backend implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, Protocol, TypeAlias

from ai_knowledge_pipeline.core.runtime import (
    ArtifactId,
    ArtifactKind,
    JobId,
    RunId,
    StageId,
    TaskId,
)
from ai_knowledge_pipeline.core.source import SourceId


ArtifactVersionId: TypeAlias = str
ArtifactSnapshotId: TypeAlias = str
ArtifactManifestVersion: TypeAlias = str
ArtifactEventId: TypeAlias = str
ArtifactGraphId: TypeAlias = str
ArtifactRelationId: TypeAlias = str
ArtifactScalar: TypeAlias = str | int | float | bool | None
ArtifactMetadataMap: TypeAlias = Mapping[
    str,
    ArtifactScalar | tuple[ArtifactScalar, ...],
]


class ArtifactStorageClass(StrEnum):
    """Logical storage class for an artifact."""

    LOCAL_FILE = "local_file"
    LOCAL_DIRECTORY = "local_directory"
    REMOTE_OBJECT = "remote_object"
    DATABASE_RECORD = "database_record"
    VIRTUAL = "virtual"


class ArtifactStatus(StrEnum):
    """Append-friendly artifact lifecycle status."""

    DECLARED = "declared"
    RESERVED = "reserved"
    MATERIALIZED = "materialized"
    REGISTERED = "registered"
    VERIFIED = "verified"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    TOMBSTONED = "tombstoned"


class ArtifactVisibility(StrEnum):
    """Who should consume an artifact."""

    INTERNAL = "internal"
    USER_FACING = "user_facing"
    AI_CONTEXT = "ai_context"
    RAG_INDEXABLE = "rag_indexable"
    AGENT_MEMORY = "agent_memory"


class IntegrityAlgorithm(StrEnum):
    """Supported integrity digest algorithms."""

    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    NONE = "none"


class ArtifactRelationType(StrEnum):
    """Relationship edge types between immutable artifact snapshots."""

    DERIVED_FROM = "derived_from"
    VERSION_OF = "version_of"
    SUPERSEDES = "supersedes"
    GENERATED_BY = "generated_by"
    CONSUMED_BY = "consumed_by"
    REFERENCES = "references"
    SPLIT_FROM = "split_from"
    MERGED_FROM = "merged_from"
    INDEXED_FROM = "indexed_from"
    MEMORY_FROM = "memory_from"


class ArtifactEventType(StrEnum):
    """Append-only artifact lifecycle events."""

    DECLARED = "artifact_declared"
    MATERIALIZED = "artifact_materialized"
    REGISTERED = "artifact_registered"
    VERIFIED = "artifact_verified"
    RELATION_RECORDED = "artifact_relation_recorded"
    VERSION_CREATED = "artifact_version_created"
    SUPERSEDED = "artifact_superseded"
    DEPRECATED = "artifact_deprecated"
    TOMBSTONED = "artifact_tombstoned"


class ArtifactConsumerKind(StrEnum):
    """Known downstream consumers for artifact metadata."""

    TRANSCRIPTION = "transcription"
    AI_CLEANING = "ai_cleaning"
    MARKDOWN_RENDERING = "markdown_rendering"
    OBSIDIAN = "obsidian"
    RAG = "rag"
    EMBEDDINGS = "embeddings"
    AGENT_MEMORY = "agent_memory"
    MCP = "mcp"


@dataclass(frozen=True, slots=True)
class ArtifactLocation:
    """Where an artifact snapshot can be found."""

    storage_class: ArtifactStorageClass
    uri: str
    path: Path | None = None
    media_type: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactIntegrity:
    """Integrity metadata for immutable artifact snapshots."""

    algorithm: IntegrityAlgorithm
    digest: str | None = None
    size_bytes: int | None = None
    verified: bool = False


@dataclass(frozen=True, slots=True)
class ArtifactVersion:
    """Version pointer for an artifact snapshot."""

    version_id: ArtifactVersionId
    version_index: int
    parent_version_id: ArtifactVersionId | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    """Stable metadata for downstream AI, RAG, and user-facing consumers."""

    title: str | None = None
    language: str | None = None
    tags: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    content_type: str | None = None
    text_format: str | None = None
    duration_seconds: float | None = None
    token_count: int | None = None
    chunk_index: int | None = None
    chunk_count: int | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    consumer_kinds: tuple[ArtifactConsumerKind, ...] = ()
    extra: ArtifactMetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactLineage:
    """Run and source context that produced an artifact snapshot."""

    source_id: SourceId | None = None
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId | None = None
    input_snapshot_ids: tuple[ArtifactSnapshotId, ...] = ()
    upstream_artifact_ids: tuple[ArtifactId, ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactSnapshot:
    """Immutable artifact snapshot registered by the pipeline."""

    artifact_id: ArtifactId
    snapshot_id: ArtifactSnapshotId
    kind: ArtifactKind
    status: ArtifactStatus
    location: ArtifactLocation
    version: ArtifactVersion
    lineage: ArtifactLineage = field(default_factory=ArtifactLineage)
    integrity: ArtifactIntegrity = field(
        default_factory=lambda: ArtifactIntegrity(
            algorithm=IntegrityAlgorithm.NONE,
        )
    )
    metadata: ArtifactMetadata = field(default_factory=ArtifactMetadata)
    visibility: tuple[ArtifactVisibility, ...] = (ArtifactVisibility.INTERNAL,)


@dataclass(frozen=True, slots=True)
class ArtifactRelationship:
    """Directed edge between two artifact snapshots."""

    relation_id: ArtifactRelationId
    relation_type: ArtifactRelationType
    from_snapshot_id: ArtifactSnapshotId
    to_snapshot_id: ArtifactSnapshotId
    metadata: ArtifactMetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactRelationshipGraph:
    """A portable relationship graph for artifact lineage queries."""

    graph_id: ArtifactGraphId
    snapshots: Mapping[ArtifactSnapshotId, ArtifactSnapshot] = field(
        default_factory=dict
    )
    relationships: tuple[ArtifactRelationship, ...] = ()
    metadata: ArtifactMetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactRegistryRecord:
    """Append-only registry record for one artifact snapshot."""

    snapshot: ArtifactSnapshot
    manifest_version: ArtifactManifestVersion = "v1"
    relationships: tuple[ArtifactRelationship, ...] = ()
    metadata: ArtifactMetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Serializable manifest containing artifact registry records."""

    manifest_version: ArtifactManifestVersion
    records: tuple[ArtifactRegistryRecord, ...]
    graph: ArtifactRelationshipGraph | None = None
    metadata: ArtifactMetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactQuery:
    """Backend-neutral query shape for artifact lookup."""

    source_id: SourceId | None = None
    run_id: RunId | None = None
    stage_id: StageId | None = None
    kind: ArtifactKind | None = None
    status: ArtifactStatus | None = None
    visibility: ArtifactVisibility | None = None
    consumer_kind: ArtifactConsumerKind | None = None
    latest_only: bool = True
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactLifecyclePolicy:
    """Policy hints for artifact retention and version behavior."""

    append_only: bool = True
    immutable_snapshots: bool = True
    keep_superseded_versions: bool = True
    verify_integrity_on_register: bool = True
    allow_tombstone: bool = True


@dataclass(frozen=True, slots=True)
class ArtifactStorageConfig:
    """Configuration knobs for artifact storage contracts."""

    registry_dir: Path = Path("data/raw/artifacts")
    content_root_dir: Path = Path("data")
    manifest_version: ArtifactManifestVersion = "v1"
    default_integrity_algorithm: IntegrityAlgorithm = IntegrityAlgorithm.SHA256
    lifecycle_policy: ArtifactLifecyclePolicy = field(
        default_factory=ArtifactLifecyclePolicy
    )


@dataclass(frozen=True, slots=True)
class ArtifactEvent:
    """Append-only artifact event."""

    event_id: ArtifactEventId
    event_type: ArtifactEventType
    snapshot_id: ArtifactSnapshotId
    artifact_id: ArtifactId
    run_id: RunId | None = None
    task_id: TaskId | None = None
    stage_id: StageId | None = None
    payload: ArtifactMetadataMap = field(default_factory=dict)


class ArtifactRegistry(Protocol):
    """Append-only artifact registry boundary."""

    def register(self, record: ArtifactRegistryRecord) -> ArtifactRegistryRecord:
        """Register a new immutable artifact snapshot."""

    def get(self, snapshot_id: ArtifactSnapshotId) -> ArtifactRegistryRecord:
        """Return one registered snapshot record."""

    def query(self, query: ArtifactQuery) -> tuple[ArtifactRegistryRecord, ...]:
        """Return records matching a backend-neutral query."""


class ArtifactRepository(Protocol):
    """Storage reference boundary for artifact manifests."""

    def save_manifest(self, manifest: ArtifactManifest) -> str:
        """Persist a manifest and return a backend-specific reference."""

    def load_manifest(self, reference: str) -> ArtifactManifest:
        """Load a manifest by backend-specific reference."""


class ArtifactIntegrityVerifier(Protocol):
    """Integrity calculation and verification boundary."""

    def describe(self, snapshot: ArtifactSnapshot) -> ArtifactIntegrity:
        """Return integrity metadata for a snapshot."""

    def verify(self, snapshot: ArtifactSnapshot) -> bool:
        """Return whether a snapshot matches its integrity metadata."""


class ArtifactLineageStore(Protocol):
    """Lineage lookup boundary."""

    def parents(self, snapshot_id: ArtifactSnapshotId) -> tuple[ArtifactSnapshotId, ...]:
        """Return direct parent snapshot ids."""

    def children(self, snapshot_id: ArtifactSnapshotId) -> tuple[ArtifactSnapshotId, ...]:
        """Return direct child snapshot ids."""


class ArtifactRelationshipGraphStore(Protocol):
    """Relationship graph persistence boundary."""

    def save_graph(self, graph: ArtifactRelationshipGraph) -> str:
        """Persist an artifact relationship graph."""

    def load_graph(self, graph_id: ArtifactGraphId) -> ArtifactRelationshipGraph:
        """Load an artifact relationship graph by id."""


class ArtifactVersionResolver(Protocol):
    """Version lookup boundary."""

    def latest(self, artifact_id: ArtifactId) -> ArtifactSnapshot:
        """Return the latest snapshot for an artifact id."""

    def version(
        self,
        artifact_id: ArtifactId,
        version_id: ArtifactVersionId,
    ) -> ArtifactSnapshot:
        """Return a specific artifact version snapshot."""


__all__ = [
    "ArtifactConsumerKind",
    "ArtifactEvent",
    "ArtifactEventId",
    "ArtifactEventType",
    "ArtifactGraphId",
    "ArtifactIntegrity",
    "ArtifactIntegrityVerifier",
    "ArtifactLifecyclePolicy",
    "ArtifactLineage",
    "ArtifactLineageStore",
    "ArtifactLocation",
    "ArtifactManifest",
    "ArtifactManifestVersion",
    "ArtifactMetadata",
    "ArtifactMetadataMap",
    "ArtifactQuery",
    "ArtifactRegistry",
    "ArtifactRegistryRecord",
    "ArtifactRelationId",
    "ArtifactRelationType",
    "ArtifactRelationship",
    "ArtifactRelationshipGraph",
    "ArtifactRelationshipGraphStore",
    "ArtifactRepository",
    "ArtifactScalar",
    "ArtifactSnapshot",
    "ArtifactSnapshotId",
    "ArtifactStatus",
    "ArtifactStorageClass",
    "ArtifactStorageConfig",
    "ArtifactVersion",
    "ArtifactVersionId",
    "ArtifactVersionResolver",
    "ArtifactVisibility",
    "IntegrityAlgorithm",
]
