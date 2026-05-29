"""Source id factory implementations."""

from __future__ import annotations

from hashlib import sha256

from ai_knowledge_pipeline.core.source import SourceId
from ai_knowledge_pipeline.modules.sources.interfaces import SourceIdFactory
from ai_knowledge_pipeline.modules.sources.types import RawSourceInput, SourceDetection


class StableSourceIdFactory(SourceIdFactory):
    """Create deterministic source ids from detection output and raw input."""

    def create_id(
        self,
        raw_input: RawSourceInput,
        detection: SourceDetection,
    ) -> SourceId:
        normalized_input = raw_input.strip()
        digest_input = f"{detection.kind.value}:{normalized_input}".encode("utf-8")
        digest = sha256(digest_input).hexdigest()[:16]
        return f"src_{detection.kind.value}_{digest}"


__all__ = ["StableSourceIdFactory"]
