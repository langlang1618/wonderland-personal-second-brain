"""Merge chunk transcript artifacts into a complete transcript."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_knowledge_pipeline.modules.transcription.runtime.types import (
    ChunkTranscriptArtifact,
)


@dataclass(frozen=True, slots=True)
class TranscriptMergeResult:
    """Output of merging chunk transcript files."""

    text: str
    path: Path | None
    chunk_count: int


class TranscriptMerger:
    """Merge chunk transcript text in chunk-index order."""

    def merge(
        self,
        artifacts: tuple[ChunkTranscriptArtifact, ...],
        output_path: Path | None = None,
    ) -> TranscriptMergeResult:
        ordered = sorted(
            artifacts,
            key=lambda artifact: artifact.transcript.chunk_index,
        )
        text = "\n\n".join(artifact.transcript.text.strip() for artifact in ordered if artifact.transcript.text.strip())
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text + "\n", encoding="utf-8")
        return TranscriptMergeResult(
            text=text,
            path=output_path,
            chunk_count=len(ordered),
        )


__all__ = ["TranscriptMergeResult", "TranscriptMerger"]
