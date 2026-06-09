"""Run one source through media ingestion, local Whisper, and Obsidian export."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlparse

from ai_knowledge_pipeline.modules.cleaning import KnowledgeProfileName
from ai_knowledge_pipeline.modules.transcription import FasterWhisperModelSize
from scripts.run_local_whisper_transcription import (
    LocalWhisperRuntimeError,
    LocalWhisperRuntimeRequest,
    LocalWhisperRuntimeResult,
    run_local_whisper_transcription,
)
from scripts.run_media_ingestion import (
    MediaIngestionBatchResult,
    MediaIngestionRequest,
    MediaIngestionStatus,
    run_media_ingestion,
)
from scripts.run_real_course_pipeline import (
    DEFAULT_DEEPSEEK_MODEL,
    RealCoursePipelineError,
    RealCoursePipelineRequest,
    RealCoursePipelineResult,
    _load_value,
    _parse_tags,
    _read_env_file,
    run_real_course_pipeline,
)


class FullCourseSourceType(StrEnum):
    """Supported full pipeline source types."""

    AUTO = "auto"
    M3U8 = "m3u8"
    WEBPAGE = "webpage"
    LOCAL_AUDIO = "local-audio"
    LOCAL_VIDEO = "local-video"


@dataclass(frozen=True, slots=True)
class FullCoursePipelineRequest:
    """Input for the single-source full auto pipeline."""

    source: str
    source_type: FullCourseSourceType = FullCourseSourceType.AUTO
    title: str | None = None
    profile: KnowledgeProfileName = KnowledgeProfileName.AI
    tags: tuple[str, ...] = ()
    model_size: FasterWhisperModelSize = FasterWhisperModelSize.SMALL
    language: str | None = "zh"
    chunk_minutes: int = 30
    vault_path: Path | None = None
    output_dir: Path = Path("data/media_ingestion")
    transcript_output_dir: Path | None = None
    model: str = DEFAULT_DEEPSEEK_MODEL
    skip_existing: bool = False
    dry_run: bool = False
    env_path: Path = Path(".env")


@dataclass(frozen=True, slots=True)
class FullCoursePipelineResult:
    """Key artifacts produced by the full auto pipeline."""

    title: str
    source_type: FullCourseSourceType
    course_dir: Path | None
    chunks_dir: Path | None
    transcript_dir: Path | None
    merged_transcript_path: Path | None
    obsidian_note_path: Path | None
    dry_run: bool = False


class FullCoursePipelineError(RuntimeError):
    """Raised when a full pipeline stage cannot complete."""


MediaIngestionRunner = Callable[[MediaIngestionRequest], MediaIngestionBatchResult]
WhisperRunner = Callable[[LocalWhisperRuntimeRequest], LocalWhisperRuntimeResult]
CourseRunner = Callable[[RealCoursePipelineRequest], RealCoursePipelineResult]


def run_full_course_pipeline(
    request: FullCoursePipelineRequest,
    *,
    media_ingestion_runner: MediaIngestionRunner = run_media_ingestion,
    whisper_runner: WhisperRunner = run_local_whisper_transcription,
    course_runner: CourseRunner = run_real_course_pipeline,
) -> FullCoursePipelineResult:
    """Run one URL-like source through the complete local-first course pipeline."""

    resolved_type = _resolve_source_type(request.source, request.source_type)
    title = _resolve_title(request.source, request.title)
    if resolved_type not in {FullCourseSourceType.M3U8, FullCourseSourceType.WEBPAGE}:
        raise FullCoursePipelineError(
            f"Source type '{resolved_type.value}' is reserved for a later stage."
        )

    media_result = media_ingestion_runner(
        MediaIngestionRequest(
            urls=(request.source,),
            output_dir=request.output_dir,
            title=title,
            chunk_minutes=request.chunk_minutes,
            dry_run=request.dry_run,
            skip_existing=request.skip_existing,
        )
    )
    media_item = _single_media_item(media_result)
    course_dir = media_item.plan.course_dir
    chunks_dir = media_item.plan.chunks_dir
    if media_item.status is MediaIngestionStatus.FAILED:
        raise FullCoursePipelineError(
            f"Media ingestion failed: {'; '.join(media_item.errors) or 'unknown error'}"
        )

    transcript_dir = _transcript_dir(request, title)
    if request.dry_run:
        return FullCoursePipelineResult(
            title=title,
            source_type=resolved_type,
            course_dir=course_dir,
            chunks_dir=chunks_dir,
            transcript_dir=transcript_dir,
            merged_transcript_path=transcript_dir / "merged_transcript.txt",
            obsidian_note_path=None,
            dry_run=True,
        )

    if not media_item.chunk_paths:
        raise FullCoursePipelineError(f"No audio chunks were produced in: {chunks_dir}")

    try:
        whisper_result = whisper_runner(
            LocalWhisperRuntimeRequest(
                chunks_dir=chunks_dir,
                output_dir=transcript_dir,
                model_size=request.model_size,
                language=request.language,
                merge=True,
            )
        )
    except LocalWhisperRuntimeError as exc:
        raise FullCoursePipelineError(f"Whisper transcription failed: {exc}") from exc
    if whisper_result.errors:
        raise FullCoursePipelineError(
            f"Whisper transcription produced errors: {'; '.join(whisper_result.errors)}"
        )
    merged_path = whisper_result.merged_transcript_path
    if merged_path is None or not merged_path.exists():
        raise FullCoursePipelineError(
            "Whisper transcription did not produce merged_transcript.txt."
        )

    vault_path = _resolve_vault_path(request)
    try:
        course_result = course_runner(
            RealCoursePipelineRequest(
                local_transcript_path=merged_path,
                obsidian_vault_path=vault_path,
                title=title,
                tags=request.tags,
                model=request.model,
                profile=request.profile,
                env_path=request.env_path,
            )
        )
    except RealCoursePipelineError as exc:
        raise FullCoursePipelineError(f"Transcript-to-Obsidian failed: {exc}") from exc

    return FullCoursePipelineResult(
        title=title,
        source_type=resolved_type,
        course_dir=course_dir,
        chunks_dir=chunks_dir,
        transcript_dir=transcript_dir,
        merged_transcript_path=merged_path,
        obsidian_note_path=course_result.obsidian_note_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for the full course pipeline runner."""

    args = _parse_args(argv)
    env_values = _read_env_file(Path(".env"))
    vault = args.vault or _load_value("OBSIDIAN_VAULT_PATH", env_values)
    model = args.model or _load_value("DEEPSEEK_MODEL", env_values) or DEFAULT_DEEPSEEK_MODEL
    request = FullCoursePipelineRequest(
        source=args.source,
        source_type=FullCourseSourceType(args.source_type),
        title=args.title,
        profile=KnowledgeProfileName(args.profile),
        tags=_parse_tags(args.tags),
        model_size=FasterWhisperModelSize(args.model_size),
        language=args.language,
        chunk_minutes=args.chunk_minutes,
        vault_path=Path(vault) if vault else None,
        output_dir=Path(args.output_dir),
        transcript_output_dir=Path(args.transcript_output_dir)
        if args.transcript_output_dir
        else None,
        model=model,
        skip_existing=args.skip_existing,
        dry_run=args.dry_run,
    )
    try:
        result = run_full_course_pipeline(request)
    except FullCoursePipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_result(result)
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one source through ingestion, local Whisper, and Obsidian export.",
    )
    parser.add_argument("--source", required=True, help="m3u8/webpage URL or future local file.")
    parser.add_argument(
        "--source-type",
        choices=tuple(source_type.value for source_type in FullCourseSourceType),
        default=FullCourseSourceType.AUTO.value,
    )
    parser.add_argument("--title", help="Optional course title.")
    parser.add_argument(
        "--profile",
        choices=tuple(profile.value for profile in KnowledgeProfileName),
        default=KnowledgeProfileName.AI.value,
    )
    parser.add_argument("--tags", help="Comma-separated note tags.")
    parser.add_argument(
        "--model-size",
        choices=tuple(model.value for model in FasterWhisperModelSize),
        default=FasterWhisperModelSize.SMALL.value,
    )
    parser.add_argument("--language", default="zh")
    parser.add_argument("--chunk-minutes", type=int, default=30)
    parser.add_argument("--vault", help="Obsidian vault path. Falls back to OBSIDIAN_VAULT_PATH.")
    parser.add_argument("--output-dir", default="data/media_ingestion")
    parser.add_argument("--transcript-output-dir")
    parser.add_argument("--model", help="DeepSeek model. Defaults to DEEPSEEK_MODEL.")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _single_media_item(media_result: MediaIngestionBatchResult):
    if not media_result.items:
        raise FullCoursePipelineError("Media ingestion returned no result items.")
    item = media_result.items[0]
    if len(media_result.items) > 1:
        raise FullCoursePipelineError("Full course pipeline accepts exactly one source.")
    return item


def _resolve_source_type(
    source: str,
    requested_type: FullCourseSourceType,
) -> FullCourseSourceType:
    if requested_type is not FullCourseSourceType.AUTO:
        return requested_type
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        return FullCourseSourceType.M3U8 if parsed.path.lower().endswith(".m3u8") else FullCourseSourceType.WEBPAGE
    path = Path(source)
    if path.suffix.lower() in {".mp3", ".m4a", ".wav", ".aac", ".flac"}:
        return FullCourseSourceType.LOCAL_AUDIO
    if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}:
        return FullCourseSourceType.LOCAL_VIDEO
    raise FullCoursePipelineError(f"Unable to detect source type for: {_display_source(source)}")


def _resolve_title(source: str, title: str | None) -> str:
    if title:
        return title
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        stem = Path(parsed.path).stem
        if stem:
            return stem
    path = Path(source)
    if path.name:
        return path.stem
    return f"course-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _transcript_dir(request: FullCoursePipelineRequest, title: str) -> Path:
    if request.transcript_output_dir is not None:
        return request.transcript_output_dir
    return Path("data/transcripts") / f"{_slugify(title)}-{request.model_size.value}"


def _resolve_vault_path(request: FullCoursePipelineRequest) -> Path:
    if request.vault_path is not None:
        return request.vault_path
    env_values = _read_env_file(request.env_path)
    vault = _load_value("OBSIDIAN_VAULT_PATH", env_values)
    if not vault:
        raise FullCoursePipelineError(
            "Obsidian vault path is required. Pass --vault or set OBSIDIAN_VAULT_PATH."
        )
    return Path(vault)


def _print_result(result: FullCoursePipelineResult) -> None:
    if result.dry_run:
        print("Full course pipeline dry-run plan:")
    else:
        print("Full course pipeline completed:")
    print(f"title: {result.title}")
    print(f"source_type: {result.source_type.value}")
    print(f"course_dir: {result.course_dir}")
    print(f"chunks_dir: {result.chunks_dir}")
    print(f"transcript_dir: {result.transcript_dir}")
    print(f"merged_transcript_path: {result.merged_transcript_path}")
    print(f"obsidian_note_path: {result.obsidian_note_path}")


def _display_source(source: str, limit: int = 90) -> str:
    parsed = urlparse(source)
    cleaned = parsed._replace(query="", fragment="").geturl() if parsed.scheme else source
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "course"


if __name__ == "__main__":
    raise SystemExit(main())
