"""Typed DTOs for the sources normalizer layer.

These objects model the boundaries between detection, parsing, validation, and
manifest persistence. They intentionally do not classify inputs or touch disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, TypeAlias

from ai_knowledge_pipeline.core.source import (
    MediaKind,
    MetadataMap,
    SourceData,
    SourceKind,
    SourceModelConfig,
)
from ai_knowledge_pipeline.modules.sources.errors import SourceIssue, SourceIssueSeverity


RawSourceInput: TypeAlias = str
ParserName: TypeAlias = str
ManifestVersion: TypeAlias = str


class DetectionSignal(StrEnum):
    """Evidence a detector may use to classify a raw input."""

    URL_SCHEME = "url_scheme"
    URL_HOST = "url_host"
    URL_PATH = "url_path"
    FILE_EXTENSION = "file_extension"
    FILE_PROBE = "file_probe"
    USER_HINT = "user_hint"


class ManifestFormat(StrEnum):
    """Supported manifest serialization targets."""

    JSON = "json"
    YAML = "yaml"


@dataclass(frozen=True, slots=True)
class SourceHint:
    """Optional caller-provided hint for safer source normalization."""

    kind: SourceKind | None = None
    media_kind: MediaKind | None = None
    title: str | None = None
    tags: tuple[str, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceParseContext:
    """Context available to detectors, parsers, and validators."""

    config: SourceModelConfig
    config_profile: str = "default"
    hint: SourceHint | None = None


@dataclass(frozen=True, slots=True)
class SourceDetection:
    """Detector output consumed by parser selection."""

    raw_input: RawSourceInput
    kind: SourceKind
    media_kind: MediaKind
    parser_name: ParserName
    confidence: float
    signals: tuple[DetectionSignal, ...] = ()
    issues: tuple[SourceIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceParseRequest:
    """Input passed into a concrete parser."""

    raw_input: RawSourceInput
    detection: SourceDetection
    context: SourceParseContext


@dataclass(frozen=True, slots=True)
class SourceParseResult:
    """Parser output before final validation and persistence."""

    source: SourceData | None
    issues: tuple[SourceIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceValidationResult:
    """Validator output for a parsed source descriptor."""

    source: SourceData
    issues: tuple[SourceIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether the result contains no error-severity issues."""

        return not any(
            issue.severity is SourceIssueSeverity.ERROR for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class SourceManifestRef:
    """Reference to a persisted source manifest."""

    source_id: str
    path: Path
    version: ManifestVersion = "v1"
    format: ManifestFormat = ManifestFormat.JSON


@dataclass(frozen=True, slots=True)
class SourceNormalizationResult:
    """Top-level output of the sources normalizer layer."""

    source: SourceData | None
    detection: SourceDetection | None = None
    manifest: SourceManifestRef | None = None
    issues: tuple[SourceIssue, ...] = ()

    @property
    def is_success(self) -> bool:
        """Return whether normalization produced a source without errors."""

        return self.source is not None and not any(
            issue.severity is SourceIssueSeverity.ERROR for issue in self.issues
        )


@dataclass(frozen=True, slots=True)
class SourceManifestEnvelope:
    """Serializable envelope for source manifests."""

    manifest_version: ManifestVersion
    source: SourceData
    parser_name: ParserName
    metadata: Mapping[str, str] = field(default_factory=dict)


__all__ = [
    "DetectionSignal",
    "ManifestFormat",
    "ManifestVersion",
    "ParserName",
    "RawSourceInput",
    "SourceDetection",
    "SourceHint",
    "SourceManifestEnvelope",
    "SourceManifestRef",
    "SourceNormalizationResult",
    "SourceParseContext",
    "SourceParseRequest",
    "SourceParseResult",
    "SourceValidationResult",
]
