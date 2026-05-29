"""Source data model contracts.

This module defines the normalized input contract shared by every pipeline
stage. It intentionally contains no source detection, download, or filesystem
mutation logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, TypeAlias, TypedDict


SourceId: TypeAlias = str
SourceURI: TypeAlias = str
Tag: TypeAlias = str
MetadataValue: TypeAlias = str | int | float | bool | None
MetadataMap: TypeAlias = Mapping[str, MetadataValue | list[MetadataValue]]


class SourceKind(StrEnum):
    """Supported high-level source families."""

    YOUTUBE = "youtube"
    M3U8 = "m3u8"
    LOCAL_VIDEO = "local_video"
    LOCAL_AUDIO = "local_audio"


class MediaKind(StrEnum):
    """Media type expected by downstream stages."""

    VIDEO = "video"
    AUDIO = "audio"


class SourceAccess(StrEnum):
    """How the pipeline should access the source."""

    REMOTE = "remote"
    LOCAL = "local"


class SourceStatus(StrEnum):
    """Lifecycle status of a normalized source descriptor."""

    DECLARED = "declared"
    READY = "ready"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceMetadataSchema(TypedDict, total=False):
    """Serializable metadata shape for source descriptors.

    The schema stays intentionally broad because not all source families expose
    the same metadata. Fields here should remain stable and safe to preserve in
    Obsidian frontmatter, RAG documents, or agent memory.
    """

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


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Where the source can be read from."""

    access: SourceAccess
    uri: SourceURI
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Human and machine readable metadata attached to a source."""

    title: str | None = None
    description: str | None = None
    author: str | None = None
    channel: str | None = None
    course: str | None = None
    episode: str | None = None
    language: str | None = None
    duration_seconds: float | None = None
    published_at: str | None = None
    captured_at: str | None = None
    source_url: str | None = None
    canonical_url: str | None = None
    local_path: Path | None = None
    origin_platform: str | None = None
    content_license: str | None = None
    tags: tuple[Tag, ...] = ()
    topics: tuple[str, ...] = ()
    external_ids: Mapping[str, str] = field(default_factory=dict)
    extra: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceData:
    """Normalized source contract passed into the pipeline."""

    source_id: SourceId
    kind: SourceKind
    media_kind: MediaKind
    location: SourceLocation
    metadata: SourceMetadata = field(default_factory=SourceMetadata)
    status: SourceStatus = SourceStatus.DECLARED
    preferred_track: Literal["audio", "video"] = "audio"
    config_profile: str = "default"


@dataclass(frozen=True, slots=True)
class SourceBatch:
    """A collection of sources submitted as one pipeline unit."""

    batch_id: str
    sources: tuple[SourceData, ...]
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceModelConfig:
    """Configuration knobs for source normalization and storage."""

    source_manifest_dir: Path = Path("data/raw/sources")
    default_language: str | None = None
    default_tags: tuple[Tag, ...] = ()
    prefer_audio: bool = True
    allow_remote_sources: bool = True
    allow_local_sources: bool = True


class SourceNormalizer(Protocol):
    """Contract for future source normalization implementations."""

    def normalize(self, raw_input: str, config: SourceModelConfig) -> SourceData:
        """Convert one raw input string into a SourceData descriptor."""


class SourceManifestStore(Protocol):
    """Contract for persisting normalized source descriptors."""

    def save(self, source: SourceData) -> Path:
        """Persist a source descriptor and return its manifest path."""

    def load(self, source_id: SourceId) -> SourceData:
        """Load a source descriptor by id."""


SourceRecord: TypeAlias = dict[str, Any]


__all__ = [
    "MediaKind",
    "MetadataMap",
    "MetadataValue",
    "SourceAccess",
    "SourceBatch",
    "SourceData",
    "SourceId",
    "SourceKind",
    "SourceLocation",
    "SourceManifestStore",
    "SourceMetadata",
    "SourceMetadataSchema",
    "SourceModelConfig",
    "SourceNormalizer",
    "SourceRecord",
    "SourceStatus",
    "SourceURI",
    "Tag",
]
