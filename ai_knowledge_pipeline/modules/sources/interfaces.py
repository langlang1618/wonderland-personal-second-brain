"""Interfaces for the sources normalizer layer.

Concrete implementations will be added later. These protocols define the
system boundary for detection, parsing, validation, id generation, and manifest
persistence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ai_knowledge_pipeline.core.source import SourceData, SourceId
from ai_knowledge_pipeline.modules.sources.types import (
    RawSourceInput,
    SourceDetection,
    SourceManifestEnvelope,
    SourceManifestRef,
    SourceNormalizationResult,
    SourceParseContext,
    SourceParseRequest,
    SourceParseResult,
    SourceValidationResult,
)


class SourceDetector(Protocol):
    """Classify raw input and select a parser candidate."""

    def detect(
        self,
        raw_input: RawSourceInput,
        context: SourceParseContext,
    ) -> SourceDetection:
        """Return source kind, media kind, confidence, and parser name."""


class SourceParser(Protocol):
    """Convert one detected raw input into a SourceData candidate."""

    name: str

    def parse(self, request: SourceParseRequest) -> SourceParseResult:
        """Parse without downloading media or mutating source files."""


class SourceValidator(Protocol):
    """Validate a SourceData candidate against config and policy."""

    def validate(
        self,
        source: SourceData,
        context: SourceParseContext,
    ) -> SourceValidationResult:
        """Return validation issues without changing the source."""


class SourceIdFactory(Protocol):
    """Create stable source ids from normalized source data."""

    def create_id(
        self,
        raw_input: RawSourceInput,
        detection: SourceDetection,
    ) -> SourceId:
        """Return a deterministic or configured source id."""


class SourceManifestSerializer(Protocol):
    """Serialize and deserialize manifest envelopes."""

    def dumps(self, envelope: SourceManifestEnvelope) -> str:
        """Serialize a manifest envelope."""

    def loads(self, payload: str) -> SourceManifestEnvelope:
        """Deserialize a manifest envelope."""


class SourceManifestRepository(Protocol):
    """Persistence boundary for normalized source manifests."""

    def save(self, envelope: SourceManifestEnvelope) -> SourceManifestRef:
        """Persist an envelope and return a manifest reference."""

    def load(self, path: Path) -> SourceManifestEnvelope:
        """Load an envelope from a manifest path."""

    def find_by_source_id(self, source_id: SourceId) -> SourceManifestRef | None:
        """Return an existing manifest reference if one is known."""


class SourcesNormalizer(Protocol):
    """Top-level orchestration boundary for source normalization."""

    def normalize(
        self,
        raw_input: RawSourceInput,
        context: SourceParseContext,
    ) -> SourceNormalizationResult:
        """Normalize one raw input into SourceData and optional manifest."""


__all__ = [
    "SourceDetector",
    "SourceIdFactory",
    "SourceManifestRepository",
    "SourceManifestSerializer",
    "SourceParser",
    "SourceValidator",
    "SourcesNormalizer",
]
