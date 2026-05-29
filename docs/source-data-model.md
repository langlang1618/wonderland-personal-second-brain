# Source Data Model

This document defines the normalized source contract for AI Knowledge Pipeline. It is a schema and typing layer only; it does not implement source detection, downloading, probing, or validation side effects.

## Module Responsibility

The Source Data Model represents one user-provided input before any media download or transcription work begins.

Supported source families:

- YouTube URL
- m3u8 URL
- local video
- local audio

The model answers four questions for downstream modules:

- What kind of source is this?
- Where can it be accessed?
- What media kind should downstream stages expect?
- What metadata should travel with the source through the pipeline?

## File Organization

```text
ai_knowledge_pipeline/
├── core/
│   └── source.py
└── modules/
    └── sources/
        └── contracts.py
```

`core/source.py`
: Owns the stable domain model used across the full pipeline.

`modules/sources/contracts.py`
: Re-exports source contracts for the future source normalization module. Concrete source detection and normalization will be added later.

`configs/default.example.yaml`
: Contains configurable source model settings such as manifest directory, default tags, default language, and whether remote or local sources are allowed.

`data/raw/sources/`
: Planned manifest location for serialized `SourceData` records. The directory is configuration-driven and will be created by a future persistence module.

## Data Structures

### SourceData

`SourceData` is the top-level object passed from source normalization into the rest of the pipeline.

Fields:

- `source_id`: stable unique id for this source descriptor
- `kind`: one of `youtube`, `m3u8`, `local_video`, `local_audio`
- `media_kind`: one of `video`, `audio`
- `location`: remote URL or local path descriptor
- `metadata`: human and machine readable metadata
- `status`: lifecycle state, initially `declared`
- `preferred_track`: default downstream track preference, initially `audio`
- `config_profile`: named config profile used to process the source

### SourceLocation

`SourceLocation` separates access strategy from raw location value.

Fields:

- `access`: `remote` or `local`
- `uri`: original URL or path-like string
- `path`: optional `Path` for local sources

### SourceMetadata

`SourceMetadata` contains stable metadata that should survive into Markdown frontmatter, RAG document metadata, and future agent memory records.

Fields:

- `title`
- `description`
- `author`
- `channel`
- `course`
- `episode`
- `language`
- `duration_seconds`
- `published_at`
- `captured_at`
- `source_url`
- `canonical_url`
- `local_path`
- `origin_platform`
- `content_license`
- `tags`
- `topics`
- `external_ids`
- `extra`

`extra` is intentionally available for provider-specific metadata, but stable pipeline logic should prefer first-class fields when possible.

### SourceBatch

`SourceBatch` groups multiple `SourceData` records into a single pipeline unit. This supports course playlists, multi-file local imports, and future batch-oriented Agent/RAG workflows.

### SourceModelConfig

`SourceModelConfig` contains configuration values used by future normalization and manifest storage code.

Fields:

- `source_manifest_dir`
- `default_language`
- `default_tags`
- `prefer_audio`
- `allow_remote_sources`
- `allow_local_sources`

## Type Definitions

The model uses standard-library `dataclass`, `StrEnum`, `TypedDict`, `Protocol`, and `TypeAlias`.

Enums:

- `SourceKind`
- `MediaKind`
- `SourceAccess`
- `SourceStatus`

Protocols:

- `SourceNormalizer`
- `SourceManifestStore`

These protocols define future implementation boundaries without committing to the implementation today.

## Metadata Schema

Serializable metadata should follow `SourceMetadataSchema`:

```python
class SourceMetadataSchema(TypedDict, total=False):
    title: str
    description: str
    author: str
    channel: str
    course: str
    episode: str
    language: str
    duration_seconds: float
    published_at: str
    captured_at: str
    source_url: str
    canonical_url: str
    local_path: str
    origin_platform: str
    content_license: str
    tags: list[str]
    topics: list[str]
    external_ids: dict[str, str]
```

This schema is designed to be safe for:

- Obsidian YAML metadata
- RAG chunk metadata
- vector database payloads
- future Agent Memory records
- LangGraph workflow state

## Why This Design

The model is placed in `core` because every downstream stage needs to depend on the same source contract. The sources module can normalize user input, but it should not own the canonical cross-pipeline data shape.

The model uses immutable dataclasses with `frozen=True` and `slots=True` so source descriptors behave like durable facts after creation. Later modules can produce new artifacts from a source, but should not mutate the original source record in place.

`SourceLocation` keeps remote and local access explicit. A YouTube URL and a local audio path are both inputs, but they have different security, caching, and retry behavior.

`SourceMetadata` separates stable metadata from `extra`. This gives the system enough structure for Obsidian, RAG, and memory while still allowing provider-specific fields from YouTube, m3u8 manifests, or local media probes.

`SourceBatch` is included early because courses and playlists are naturally multi-item inputs. This prevents the future pipeline from being designed around only one file at a time.

`Protocol` contracts make the next implementation steps testable. A fake normalizer or fake manifest store can be used in unit tests without requiring network, yt-dlp, ffmpeg, Whisper, or OpenAI.

## Pipeline Flow

```text
Raw input string
  -> SourceNormalizer contract
  -> SourceData
  -> optional SourceManifestStore contract
  -> download module reads SourceData
  -> chunking module inherits SourceData metadata
  -> transcription attaches transcript artifacts to source_id
  -> cleaning uses SourceMetadata as AI context
  -> markdown maps SourceMetadata into YAML frontmatter
  -> obsidian routes output using tags, topics, course, and title
```

The important rule is that `SourceData` becomes the identity anchor for all later artifacts. Media files, chunks, transcripts, cleaned documents, Markdown files, embeddings, and memory records should be traceable back to `source_id`.

## Example Shape

```python
SourceData(
    source_id="src_...",
    kind=SourceKind.YOUTUBE,
    media_kind=MediaKind.VIDEO,
    location=SourceLocation(
        access=SourceAccess.REMOTE,
        uri="https://www.youtube.com/watch?v=...",
    ),
    metadata=SourceMetadata(
        title="Course lecture",
        origin_platform="youtube",
        tags=("course", "ai"),
    ),
)
```

This is an example shape only. Actual source id generation and input classification will be implemented later.
