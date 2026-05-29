# Artifact Storage Layer

This document designs the artifact storage boundary for AI Knowledge Pipeline. It defines schemas, typing, protocols, and runtime contracts only. It does not implement downloader logic, file IO, database writes, hashing, or storage backends.

## Goals

The artifact layer must support:

- append-only registration
- resumable pipeline runs
- immutable artifact snapshots
- auditability
- transcript versioning
- Markdown regeneration
- RAG chunk rebuild
- embedding re-index
- AI cleaning re-run
- agent memory evolution
- multiple downstream AI consumers

## Directory Structure

```text
ai_knowledge_pipeline/
└── core/
    └── artifact.py

data/
├── raw/
│   └── artifacts/
├── media/
├── chunks/
├── transcripts/
│   ├── raw/
│   └── cleaned/
├── markdown/
└── obsidian/
```

`core/artifact.py`
: Canonical artifact contracts for snapshots, versions, lineage, integrity, registry records, manifests, and repository protocols.

`data/raw/artifacts/`
: Planned registry and manifest location for artifact records. Actual file IO will be implemented later behind repository protocols.

The artifact layer describes storage, but does not perform storage.

## Core Model

The central object is `ArtifactSnapshot`.

An artifact id represents a logical artifact. A snapshot id represents one immutable point-in-time version of that artifact.

```text
artifact_id: transcript_src_1
  snapshot_id: transcript_src_1_v1
  snapshot_id: transcript_src_1_v2
  snapshot_id: transcript_src_1_v3
```

This distinction is what enables transcript versioning, Markdown regeneration, RAG rebuilds, and audit-friendly AI re-runs.

## Dataclass / Enum / Protocol Design

Primary dataclasses:

- `ArtifactLocation`
- `ArtifactIntegrity`
- `ArtifactVersion`
- `ArtifactMetadata`
- `ArtifactLineage`
- `ArtifactSnapshot`
- `ArtifactRelationship`
- `ArtifactRelationshipGraph`
- `ArtifactRegistryRecord`
- `ArtifactManifest`
- `ArtifactQuery`
- `ArtifactLifecyclePolicy`
- `ArtifactStorageConfig`
- `ArtifactEvent`

Primary enums:

- `ArtifactStorageClass`
- `ArtifactStatus`
- `ArtifactVisibility`
- `IntegrityAlgorithm`
- `ArtifactRelationType`
- `ArtifactEventType`
- `ArtifactConsumerKind`

Primary protocols:

- `ArtifactRegistry`
- `ArtifactRepository`
- `ArtifactIntegrityVerifier`
- `ArtifactLineageStore`
- `ArtifactRelationshipGraphStore`
- `ArtifactVersionResolver`

## Artifact Data Flow

```text
stage produces logical output
  -> creates ArtifactSnapshot contract
  -> attaches ArtifactLineage
  -> attaches ArtifactIntegrity metadata
  -> records ArtifactRelationship edges
  -> registers ArtifactRegistryRecord
  -> emits ArtifactEvent
  -> runtime records lightweight RuntimeArtifact reference
```

The runtime can keep lightweight artifact references. The artifact layer keeps the full registry contract.

## Lifecycle Design

Artifact statuses:

- `declared`
- `reserved`
- `materialized`
- `registered`
- `verified`
- `superseded`
- `deprecated`
- `tombstoned`

Recommended lifecycle:

```text
declared
  -> reserved
  -> materialized
  -> registered
  -> verified
  -> superseded / deprecated / tombstoned
```

Snapshots are immutable. A re-run creates a new snapshot instead of editing the previous snapshot.

For example, an AI cleaning re-run should produce:

```text
clean_transcript_v1
  -> clean_transcript_v2
```

with `clean_transcript_v2` related to `clean_transcript_v1` through `SUPERSEDES` or `VERSION_OF`.

## Metadata Schema

`ArtifactMetadata` is designed for both human-facing and AI-facing consumers.

Stable fields:

- title
- language
- tags
- topics
- content type
- text format
- duration seconds
- token count
- chunk index
- chunk count
- model name
- prompt version
- consumer kinds
- extra metadata

Consumer kinds:

- transcription
- AI cleaning
- Markdown rendering
- Obsidian
- RAG
- embeddings
- agent memory
- MCP

This lets one artifact advertise whether it is safe for RAG indexing, embedding generation, or agent memory.

## Versioning Strategy

Versioning is append-only:

- every re-run creates a new `ArtifactSnapshot`
- every snapshot has an `ArtifactVersion`
- parent versions are linked through `parent_version_id`
- graph edges preserve relationships across versions
- old versions remain queryable unless tombstoned by policy

This supports:

- transcript versioning
- prompt-version comparisons
- model migration experiments
- Markdown regeneration from a previous cleaned transcript
- embedding re-index from a selected Markdown version

## Lineage Design

`ArtifactLineage` records:

- source id
- run id
- job id
- task id
- stage id
- input snapshot ids
- upstream artifact ids

This allows every downstream artifact to answer:

- Which source produced me?
- Which run produced me?
- Which stage produced me?
- Which exact input snapshots did I consume?
- Can I be rebuilt if an upstream snapshot changes?

## Hash / Integrity Design

`ArtifactIntegrity` records:

- digest algorithm
- digest
- size bytes
- verified flag

Supported algorithms:

- sha256
- sha512
- blake2b
- none

The integrity verifier is a protocol:

```python
class ArtifactIntegrityVerifier(Protocol):
    def describe(self, snapshot: ArtifactSnapshot) -> ArtifactIntegrity:
        ...

    def verify(self, snapshot: ArtifactSnapshot) -> bool:
        ...
```

The schema supports integrity checks without implementing file reads today.

## Relationship Graph

`ArtifactRelationshipGraph` stores immutable snapshots as nodes and typed relationships as edges.

Relationship types:

- derived from
- version of
- supersedes
- generated by
- consumed by
- references
- split from
- merged from
- indexed from
- memory from

Example:

```text
source_manifest
  -> media
  -> chunk
  -> raw_transcript
  -> clean_transcript
  -> markdown
  -> rag_chunks
  -> embeddings
  -> agent_memory
```

The graph allows selective rebuilds. If `clean_transcript_v3` is created, Markdown, RAG chunks, embeddings, and memory can be rebuilt from that branch without destroying earlier versions.

## Registry / Repository Contracts

`ArtifactRegistry` is append-only and query-oriented:

- register a snapshot record
- get a snapshot record
- query records by source, run, stage, kind, visibility, consumer, or tags

`ArtifactRepository` manages manifest references:

- save manifest
- load manifest

`ArtifactRelationshipGraphStore` and `ArtifactLineageStore` keep graph traversal separate from basic registry lookup.

This separation keeps the system compatible with local JSON files first, then SQLite, DuckDB, vector databases, object stores, or distributed metadata services later.

## Why This Design

The pipeline will produce many intermediate artifacts. Treating them as disposable files would make retries, rebuilds, and audit trails fragile.

Immutable snapshots make outputs reproducible. Append-only registry records make runs auditable. Lineage and relationships make downstream rebuilds possible. Integrity metadata makes local-first storage safer. Visibility and consumer metadata make the same artifact useful to Obsidian, RAG, embeddings, MCP, and agent memory without hard-coding those systems into business modules.

## Supporting Agent And RAG

Agent/RAG support comes from four design choices:

- `ArtifactVisibility` marks artifacts as AI context, RAG indexable, or agent memory.
- `ArtifactConsumerKind` records intended downstream consumers.
- `ArtifactLineage` links AI outputs back to exact inputs and stages.
- `ArtifactRelationshipGraph` lets agents reason about what should be rebuilt.

Future agent tasks can ask:

- Which cleaned transcript snapshot should I summarize?
- Which Markdown notes are stale after an AI cleaning re-run?
- Which embeddings were built from an older Markdown version?
- Which memory entries came from superseded content?

The artifact layer gives those questions a typed, queryable foundation.
