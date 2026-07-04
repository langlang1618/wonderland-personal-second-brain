"""Transcribe local audio chunks with faster-whisper."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ai_knowledge_pipeline.core.artifact import (
    ArtifactLineage,
    ArtifactLocation,
    ArtifactMetadata,
    ArtifactSnapshot,
    ArtifactStatus,
    ArtifactStorageClass,
    ArtifactVersion,
)
from ai_knowledge_pipeline.core.runtime import ArtifactKind
from ai_knowledge_pipeline.infra.runtime_logging import (
    STAGE_WHISPER_TRANSCRIPTION,
    RuntimeLogger,
    create_runtime_logger,
)
from ai_knowledge_pipeline.modules.chunking import (
    MediaChunkArtifact,
    MediaChunkingStatus,
)
from ai_knowledge_pipeline.modules.transcription import (
    ChunkTranscriptArtifact,
    FasterWhisperConfig,
    FasterWhisperModelSize,
    FasterWhisperProvider,
    TranscriptArtifact,
    TranscriptMerger,
    TranscriptionConfig,
    TranscriptionErrorCode,
    TranscriptionProviderKind,
    TranscriptionRequest,
    create_default_transcriber,
)


SUPPORTED_AUDIO_SUFFIXES = (".mp3", ".m4a", ".wav", ".aac", ".flac")


@dataclass(frozen=True, slots=True)
class LocalWhisperRuntimeRequest:
    """Input for local faster-whisper chunk transcription."""

    chunks_dir: Path
    output_dir: Path
    model_size: FasterWhisperModelSize = FasterWhisperModelSize.SMALL
    language: str | None = "zh"
    merge: bool = False


@dataclass(frozen=True, slots=True)
class LocalWhisperRuntimeResult:
    """Output of local faster-whisper chunk transcription."""

    chunk_transcripts: tuple[ChunkTranscriptArtifact, ...]
    merged_transcript_path: Path | None
    manifest_path: Path
    errors: tuple[str, ...] = ()


class LocalWhisperRuntimeError(RuntimeError):
    """Raised when the local whisper runtime cannot start."""


def run_local_whisper_transcription(
    request: LocalWhisperRuntimeRequest,
    provider: FasterWhisperProvider | None = None,
    logger: RuntimeLogger | None = None,
) -> LocalWhisperRuntimeResult:
    """Transcribe each chunk file and optionally merge transcripts."""

    runtime_logger = logger or create_runtime_logger()
    model_size = _model_size(request.model_size)
    chunk_paths = scan_chunk_files(request.chunks_dir)
    if not chunk_paths:
        raise LocalWhisperRuntimeError(f"No audio chunks found: {request.chunks_dir}")
    request.output_dir.mkdir(parents=True, exist_ok=True)
    provider = provider or FasterWhisperProvider(
        FasterWhisperConfig(
            model_size=model_size,
            language=request.language,
        )
    )
    transcriber = create_default_transcriber(provider=provider)
    chunk_transcripts: list[ChunkTranscriptArtifact] = []
    errors: list[str] = []

    with runtime_logger.stage(STAGE_WHISPER_TRANSCRIPTION):
        total_chunks = len(chunk_paths)
        for index, chunk_path in enumerate(chunk_paths, start=1):
            with runtime_logger.chunk(
                STAGE_WHISPER_TRANSCRIPTION,
                chunk_index=index,
                total_chunks=total_chunks,
                chunk_name=chunk_path.name,
            ):
                chunk = _chunk_artifact(chunk_path, index, total_chunks, request.chunks_dir)
                result = transcriber.transcribe(
                    TranscriptionRequest(
                        chunk=chunk,
                        config=TranscriptionConfig(
                            raw_transcripts_dir=request.output_dir,
                            provider=TranscriptionProviderKind.FASTER_WHISPER,
                            language=request.language,
                            model_name=model_size.value,
                        ),
                        task_id=f"local-whisper-{index:03d}",
                    )
            )
            if not result.is_success or result.transcript is None:
                if _is_empty_transcript_result(result):
                    warning = _empty_chunk_warning(index, total_chunks)
                    runtime_logger.warning(warning)
                    errors.append(f"{chunk_path}: {warning}")
                    continue
                error = f"{chunk_path}: {result.issues}"
                runtime_logger.warning(error)
                errors.append(error)
                continue
            if not result.transcript.text.strip():
                warning = _empty_chunk_warning(index, total_chunks)
                runtime_logger.warning(warning)
                errors.append(f"{chunk_path}: {warning}")
                continue
            text_path = request.output_dir / f"chunk_{index:03d}.txt"
            text_path.write_text(result.transcript.text + "\n", encoding="utf-8")
            chunk_transcripts.append(
                ChunkTranscriptArtifact(
                    transcript=result.transcript,
                    text_path=text_path,
                    metadata={"chunk_path": str(chunk_path)},
                )
            )

    merged_path = None
    if request.merge and chunk_transcripts:
        merged_path = request.output_dir / "merged_transcript.txt"
        TranscriptMerger().merge(tuple(chunk_transcripts), merged_path)

    manifest_path = request.output_dir / "manifest.json"
    _write_manifest(
        manifest_path=manifest_path,
        request=request,
        chunk_transcripts=tuple(chunk_transcripts),
        merged_path=merged_path,
        errors=tuple(errors),
    )
    return LocalWhisperRuntimeResult(
        chunk_transcripts=tuple(chunk_transcripts),
        merged_transcript_path=merged_path,
        manifest_path=manifest_path,
        errors=tuple(errors),
    )


def scan_chunk_files(chunks_dir: Path) -> tuple[Path, ...]:
    """Scan supported audio chunks in natural filename order."""

    if not chunks_dir.exists() or not chunks_dir.is_dir():
        raise LocalWhisperRuntimeError(f"Chunks directory does not exist: {chunks_dir}")
    return tuple(
        sorted(
            (
                path
                for path in chunks_dir.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES
            ),
            key=lambda path: _natural_sort_key(path.name),
        )
    )


def _is_empty_transcript_result(result) -> bool:
    return any(
        issue.code is TranscriptionErrorCode.INVALID_PROVIDER_RESULT
        and "no transcript text" in issue.message.lower()
        for issue in result.issues
    )


def _empty_chunk_warning(index: int, total_chunks: int) -> str:
    return (
        f"{STAGE_WHISPER_TRANSCRIPTION} | "
        f"Chunk {index} / {total_chunks} returned empty transcript; skipped."
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run_local_whisper_transcription(
            LocalWhisperRuntimeRequest(
                chunks_dir=Path(args.chunks_dir),
                output_dir=Path(args.output_dir),
                model_size=FasterWhisperModelSize(args.model_size),
                language=args.language,
                merge=args.merge,
            )
        )
    except LocalWhisperRuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for artifact in result.chunk_transcripts:
        print(artifact.text_path)
    if result.merged_transcript_path is not None:
        print(result.merged_transcript_path)
    if result.errors:
        for error in result.errors:
            print(f"Error: {error}", file=sys.stderr)
        if not result.chunk_transcripts:
            return 1
    return 0


def _chunk_artifact(
    path: Path,
    index: int,
    chunk_count: int,
    chunks_dir: Path,
) -> MediaChunkArtifact:
    chunk_index = index - 1
    source_id = _slugify(chunks_dir.parent.name or chunks_dir.name or "local_chunks")
    artifact_id = f"chunk_{source_id}_{chunk_index:04d}"
    snapshot = ArtifactSnapshot(
        artifact_id=artifact_id,
        snapshot_id=f"{artifact_id}_v1",
        kind=ArtifactKind.CHUNK,
        status=ArtifactStatus.MATERIALIZED,
        location=ArtifactLocation(
            storage_class=ArtifactStorageClass.LOCAL_FILE,
            uri=path.as_uri() if path.is_absolute() else f"file://{path}",
            path=path,
            media_type="audio/*",
        ),
        version=ArtifactVersion(version_id="v1", version_index=1),
        lineage=ArtifactLineage(
            source_id=source_id,
            input_snapshot_ids=(f"media_{source_id}_v1",),
            upstream_artifact_ids=(f"media_{source_id}",),
        ),
        metadata=ArtifactMetadata(
            title=source_id,
            language=None,
            tags=("local-whisper",),
            duration_seconds=0,
            chunk_index=chunk_index,
            chunk_count=chunk_count,
        ),
    )
    return MediaChunkArtifact(
        chunk_artifact_id=artifact_id,
        source_id=source_id,
        parent_media_artifact_id=f"media_{source_id}",
        chunk_index=chunk_index,
        start_time=0,
        end_time=0,
        duration=0,
        status=MediaChunkingStatus.MATERIALIZED,
        path=path,
        uri=path.as_uri() if path.is_absolute() else f"file://{path}",
        snapshot=snapshot,
    )


def _write_manifest(
    *,
    manifest_path: Path,
    request: LocalWhisperRuntimeRequest,
    chunk_transcripts: tuple[ChunkTranscriptArtifact, ...],
    merged_path: Path | None,
    errors: tuple[str, ...],
) -> None:
    payload = {
        "model": _model_size(request.model_size).value,
        "language": request.language,
        "chunk_count": len(chunk_transcripts),
        "transcript_files": [str(artifact.text_path) for artifact in chunk_transcripts],
        "merged_transcript_path": str(merged_path) if merged_path else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "errors": list(errors),
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe local audio chunks.")
    parser.add_argument("--chunks-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--model-size",
        choices=tuple(model.value for model in FasterWhisperModelSize),
        default=FasterWhisperModelSize.SMALL.value,
    )
    parser.add_argument("--language", default="zh")
    parser.add_argument("--merge", action="store_true")
    return parser.parse_args(argv)


def _model_size(value) -> FasterWhisperModelSize:
    return value if isinstance(value, FasterWhisperModelSize) else FasterWhisperModelSize(value)


def _natural_sort_key(value: str) -> tuple[int | str, ...]:
    parts = re.split(r"(\d+)", value)
    return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "local-chunks"


if __name__ == "__main__":
    raise SystemExit(main())
