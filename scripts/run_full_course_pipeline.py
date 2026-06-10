"""Run one source through media ingestion, local Whisper, and Obsidian export."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, Protocol, Sequence
from urllib.parse import urlparse

from ai_knowledge_pipeline.modules.chunking.runner import SubprocessFfmpegRunner
from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkCommand,
    ChunkProcessResult,
    MediaChunkingConfig,
)
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


class CleanupSelection(StrEnum):
    """User-facing cleanup selections for generated media artifacts."""

    NONE = "none"
    RAW = "raw"
    CHUNKS = "chunks"
    RAW_CHUNKS = "raw,chunks"
    ALL_MEDIA = "all-media"


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
    cleanup: str = CleanupSelection.NONE.value


@dataclass(frozen=True, slots=True)
class CleanupPolicy:
    """Normalized cleanup policy."""

    value: str
    remove_raw: bool = False
    remove_chunks: bool = False


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Cleanup outcome after a successful full pipeline run."""

    policy: CleanupPolicy
    removed: tuple[Path, ...] = ()
    skipped: tuple[str, ...] = ()
    plan: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FullCoursePipelineResult:
    """Key artifacts produced by the full auto pipeline."""

    title: str
    source_type: FullCourseSourceType
    course_dir: Path | None
    raw_audio_path: Path | None
    chunks_dir: Path | None
    transcript_dir: Path | None
    merged_transcript_path: Path | None
    obsidian_note_path: Path | None
    cleanup: str = CleanupSelection.NONE.value
    cleanup_removed: tuple[Path, ...] = ()
    cleanup_skipped: tuple[str, ...] = ()
    cleanup_plan: tuple[str, ...] = ()
    dry_run: bool = False


class FullCoursePipelineError(RuntimeError):
    """Raised when a full pipeline stage cannot complete."""


MediaIngestionRunner = Callable[[MediaIngestionRequest], MediaIngestionBatchResult]
WhisperRunner = Callable[[LocalWhisperRuntimeRequest], LocalWhisperRuntimeResult]
CourseRunner = Callable[[RealCoursePipelineRequest], RealCoursePipelineResult]


class FfmpegRunner(Protocol):
    """Minimal ffmpeg runner protocol used by the full runner local-ingestion path."""

    def run(
        self,
        command: ChunkCommand,
        config: MediaChunkingConfig,
    ) -> ChunkProcessResult: ...


@dataclass(frozen=True, slots=True)
class LocalMediaIngestionResult:
    """Filesystem result for local audio/video ingestion."""

    course_dir: Path
    raw_audio_path: Path
    chunks_dir: Path
    chunk_paths: tuple[Path, ...] = ()


SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".aac", ".flac"}
SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}
OUTPUT_AUDIO_FORMAT = "mp3"


def run_full_course_pipeline(
    request: FullCoursePipelineRequest,
    *,
    media_ingestion_runner: MediaIngestionRunner = run_media_ingestion,
    whisper_runner: WhisperRunner = run_local_whisper_transcription,
    course_runner: CourseRunner = run_real_course_pipeline,
    ffmpeg_runner: FfmpegRunner | None = None,
) -> FullCoursePipelineResult:
    """Run one URL-like source through the complete local-first course pipeline."""

    resolved_type = _resolve_source_type(request.source, request.source_type)
    title = _resolve_title(request.source, request.title)
    cleanup_policy = _parse_cleanup(request.cleanup)
    if resolved_type in {FullCourseSourceType.M3U8, FullCourseSourceType.WEBPAGE}:
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
        raw_audio_path = media_item.plan.downloaded_audio_path
        chunks_dir = media_item.plan.chunks_dir
        chunk_paths = media_item.chunk_paths
        if media_item.status is MediaIngestionStatus.FAILED:
            raise FullCoursePipelineError(
                f"Media ingestion failed: {'; '.join(media_item.errors) or 'unknown error'}"
            )
    else:
        local_result = _run_local_media_ingestion(
            request,
            title=title,
            source_type=resolved_type,
            ffmpeg_runner=ffmpeg_runner or SubprocessFfmpegRunner(),
        )
        course_dir = local_result.course_dir
        raw_audio_path = local_result.raw_audio_path
        chunks_dir = local_result.chunks_dir
        chunk_paths = local_result.chunk_paths

    transcript_dir = _transcript_dir(request, title)
    if request.dry_run:
        cleanup_result = _cleanup_plan(
            policy=cleanup_policy,
            course_dir=course_dir,
            raw_audio_path=raw_audio_path,
            chunks_dir=chunks_dir,
        )
        return FullCoursePipelineResult(
            title=title,
            source_type=resolved_type,
            course_dir=course_dir,
            raw_audio_path=raw_audio_path,
            chunks_dir=chunks_dir,
            transcript_dir=transcript_dir,
            merged_transcript_path=transcript_dir / "merged_transcript.txt",
            obsidian_note_path=None,
            cleanup=cleanup_policy.value,
            cleanup_plan=cleanup_result.plan,
            dry_run=True,
        )

    if not chunk_paths:
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

    cleanup_result = _run_cleanup(
        policy=cleanup_policy,
        course_dir=course_dir,
        raw_audio_path=raw_audio_path,
        chunks_dir=chunks_dir,
    )
    return FullCoursePipelineResult(
        title=title,
        source_type=resolved_type,
        course_dir=course_dir,
        raw_audio_path=raw_audio_path,
        chunks_dir=chunks_dir,
        transcript_dir=transcript_dir,
        merged_transcript_path=merged_path,
        obsidian_note_path=course_result.obsidian_note_path,
        cleanup=cleanup_result.policy.value,
        cleanup_removed=cleanup_result.removed,
        cleanup_skipped=cleanup_result.skipped,
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
        cleanup=args.cleanup,
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
    parser.add_argument(
        "--cleanup",
        type=_cleanup_arg,
        default=CleanupSelection.NONE.value,
        metavar="POLICY",
        help="Cleanup generated media artifacts after a successful run.",
    )
    return parser.parse_args(argv)


def _cleanup_arg(value: str) -> str:
    try:
        CleanupSelection(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "cleanup must be one of: none, raw, chunks, raw,chunks, all-media"
        ) from exc
    return value


def _single_media_item(media_result: MediaIngestionBatchResult):
    if not media_result.items:
        raise FullCoursePipelineError("Media ingestion returned no result items.")
    item = media_result.items[0]
    if len(media_result.items) > 1:
        raise FullCoursePipelineError("Full course pipeline accepts exactly one source.")
    return item


def _run_local_media_ingestion(
    request: FullCoursePipelineRequest,
    *,
    title: str,
    source_type: FullCourseSourceType,
    ffmpeg_runner: FfmpegRunner,
) -> LocalMediaIngestionResult:
    source_path = Path(request.source).expanduser()
    _validate_local_source(source_path, source_type)
    course_dir = request.output_dir / _slugify(title)
    raw_audio_dir = course_dir / "raw_audio"
    chunks_dir = course_dir / "chunks"
    raw_audio_path = (
        raw_audio_dir / f"course{source_path.suffix.lower()}"
        if source_type is FullCourseSourceType.LOCAL_AUDIO
        else raw_audio_dir / f"course.{OUTPUT_AUDIO_FORMAT}"
    )

    if request.dry_run:
        return LocalMediaIngestionResult(
            course_dir=course_dir,
            raw_audio_path=raw_audio_path,
            chunks_dir=chunks_dir,
        )

    if request.skip_existing and raw_audio_path.exists():
        existing_chunks = _chunk_paths(chunks_dir)
        if existing_chunks:
            return LocalMediaIngestionResult(
                course_dir=course_dir,
                raw_audio_path=raw_audio_path,
                chunks_dir=chunks_dir,
                chunk_paths=existing_chunks,
            )

    raw_audio_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    if source_type is FullCourseSourceType.LOCAL_AUDIO:
        _copy_or_normalize_local_audio(
            source_path=source_path,
            raw_audio_path=raw_audio_path,
            skip_existing=request.skip_existing,
        )
    else:
        _extract_audio_from_local_video(
            source_path=source_path,
            raw_audio_path=raw_audio_path,
            ffmpeg_runner=ffmpeg_runner,
            skip_existing=request.skip_existing,
        )

    chunk_paths = _chunk_local_audio(
        raw_audio_path=raw_audio_path,
        chunks_dir=chunks_dir,
        chunk_minutes=request.chunk_minutes,
        ffmpeg_runner=ffmpeg_runner,
        skip_existing=request.skip_existing,
    )
    return LocalMediaIngestionResult(
        course_dir=course_dir,
        raw_audio_path=raw_audio_path,
        chunks_dir=chunks_dir,
        chunk_paths=chunk_paths,
    )


def _validate_local_source(source_path: Path, source_type: FullCourseSourceType) -> None:
    if not source_path.exists():
        raise FullCoursePipelineError(f"local source does not exist: {source_path}")
    if not source_path.is_file():
        raise FullCoursePipelineError(f"local source is not a file: {source_path}")
    suffix = source_path.suffix.lower()
    if source_type is FullCourseSourceType.LOCAL_AUDIO and suffix not in SUPPORTED_AUDIO_SUFFIXES:
        raise FullCoursePipelineError(
            f"Unsupported local-audio extension: {suffix or '<none>'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_SUFFIXES))}"
        )
    if source_type is FullCourseSourceType.LOCAL_VIDEO and suffix not in SUPPORTED_VIDEO_SUFFIXES:
        raise FullCoursePipelineError(
            f"Unsupported local-video extension: {suffix or '<none>'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_VIDEO_SUFFIXES))}"
        )


def _copy_or_normalize_local_audio(
    *,
    source_path: Path,
    raw_audio_path: Path,
    skip_existing: bool,
) -> None:
    if skip_existing and raw_audio_path.exists():
        return
    if source_path.resolve() == raw_audio_path.resolve():
        return
    shutil.copy2(source_path, raw_audio_path)


def _extract_audio_from_local_video(
    *,
    source_path: Path,
    raw_audio_path: Path,
    ffmpeg_runner: FfmpegRunner,
    skip_existing: bool,
) -> None:
    if skip_existing and raw_audio_path.exists():
        return
    command = (
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        str(raw_audio_path),
    )
    result = ffmpeg_runner.run(command, MediaChunkingConfig(ffmpeg_binary=command[0]))
    if result.returncode != 0:
        raise FullCoursePipelineError(
            f"ffmpeg audio extraction failed: {_excerpt(result.output.stderr)}"
        )


def _chunk_local_audio(
    *,
    raw_audio_path: Path,
    chunks_dir: Path,
    chunk_minutes: int,
    ffmpeg_runner: FfmpegRunner,
    skip_existing: bool,
) -> tuple[Path, ...]:
    if skip_existing:
        existing_chunks = _chunk_paths(chunks_dir)
        if existing_chunks:
            return existing_chunks
    chunk_pattern = chunks_dir / f"chunk_%03d.{OUTPUT_AUDIO_FORMAT}"
    command = (
        "ffmpeg",
        "-y",
        "-i",
        str(raw_audio_path),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_minutes * 60),
        "-segment_start_number",
        "1",
        "-vn",
        "-codec:a",
        "libmp3lame",
        str(chunk_pattern),
    )
    result = ffmpeg_runner.run(command, MediaChunkingConfig(ffmpeg_binary=command[0]))
    if result.returncode != 0:
        raise FullCoursePipelineError(
            f"ffmpeg chunking failed: {_excerpt(result.output.stderr)}"
        )
    chunk_paths = _chunk_paths(chunks_dir)
    if not chunk_paths:
        raise FullCoursePipelineError(f"No audio chunks were produced in: {chunks_dir}")
    return chunk_paths


def _chunk_paths(chunks_dir: Path) -> tuple[Path, ...]:
    if not chunks_dir.exists():
        return ()
    return tuple(sorted(chunks_dir.glob(f"chunk_*.{OUTPUT_AUDIO_FORMAT}")))


def _parse_cleanup(value: str) -> CleanupPolicy:
    try:
        selection = CleanupSelection(value)
    except ValueError as exc:
        raise FullCoursePipelineError(
            "Invalid cleanup policy. Use one of: "
            f"{', '.join(selection.value for selection in CleanupSelection)}"
        ) from exc
    if selection is CleanupSelection.NONE:
        return CleanupPolicy(value=selection.value)
    if selection is CleanupSelection.RAW:
        return CleanupPolicy(value=selection.value, remove_raw=True)
    if selection is CleanupSelection.CHUNKS:
        return CleanupPolicy(value=selection.value, remove_chunks=True)
    return CleanupPolicy(value=selection.value, remove_raw=True, remove_chunks=True)


def _cleanup_plan(
    *,
    policy: CleanupPolicy,
    course_dir: Path,
    raw_audio_path: Path | None,
    chunks_dir: Path | None,
) -> CleanupResult:
    plan: list[str] = []
    if policy.remove_raw and raw_audio_path is not None:
        plan.append(f"would remove {_raw_audio_dir(course_dir, raw_audio_path)}")
    if policy.remove_chunks and chunks_dir is not None:
        plan.append(f"would remove {chunks_dir}")
    return CleanupResult(policy=policy, plan=tuple(plan))


def _run_cleanup(
    *,
    policy: CleanupPolicy,
    course_dir: Path,
    raw_audio_path: Path | None,
    chunks_dir: Path | None,
) -> CleanupResult:
    removed: list[Path] = []
    skipped: list[str] = []
    if policy.remove_raw:
        if raw_audio_path is None:
            skipped.append("raw_audio: no raw audio path")
        else:
            _remove_generated_media_path(
                course_dir=course_dir,
                target=_raw_audio_dir(course_dir, raw_audio_path),
                expected_name="raw_audio",
                removed=removed,
                skipped=skipped,
            )
    if policy.remove_chunks:
        if chunks_dir is None:
            skipped.append("chunks: no chunks path")
        else:
            _remove_generated_media_path(
                course_dir=course_dir,
                target=chunks_dir,
                expected_name="chunks",
                removed=removed,
                skipped=skipped,
            )
    return CleanupResult(
        policy=policy,
        removed=tuple(removed),
        skipped=tuple(skipped),
    )


def _remove_generated_media_path(
    *,
    course_dir: Path,
    target: Path,
    expected_name: str,
    removed: list[Path],
    skipped: list[str],
) -> None:
    if target.name != expected_name:
        raise FullCoursePipelineError(
            f"Cleanup refused unsafe target name: {target}"
        )
    if not _is_safe_child_path(course_dir, target):
        raise FullCoursePipelineError(
            f"Cleanup refused path outside course_dir: {target}"
        )
    if not target.exists():
        skipped.append(f"{expected_name}: path does not exist")
        return
    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as exc:
        raise FullCoursePipelineError(f"Cleanup failed for {target}: {exc}") from exc
    removed.append(target)


def _raw_audio_dir(course_dir: Path, raw_audio_path: Path) -> Path:
    raw_audio_dir = raw_audio_path.parent
    expected = course_dir / "raw_audio"
    return raw_audio_dir if raw_audio_dir == expected else expected


def _is_safe_child_path(parent: Path, child: Path) -> bool:
    try:
        parent_resolved = parent.resolve()
        child_resolved = child.resolve()
    except OSError:
        return False
    if parent_resolved == child_resolved:
        return False
    if child_resolved.anchor == str(child_resolved):
        return False
    forbidden = {
        Path.home().resolve(),
        Path.cwd().resolve(),
    }
    if child_resolved in forbidden:
        return False
    return parent_resolved in child_resolved.parents


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
    if path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES:
        return FullCourseSourceType.LOCAL_AUDIO
    if path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES:
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
    model_size = (
        request.model_size.value
        if isinstance(request.model_size, FasterWhisperModelSize)
        else str(request.model_size)
    )
    return Path("data/transcripts") / f"{_slugify(title)}-{model_size}"


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
    print(f"raw_audio_path: {result.raw_audio_path}")
    print(f"chunks_dir: {result.chunks_dir}")
    print(f"transcript_dir: {result.transcript_dir}")
    print(f"merged_transcript_path: {result.merged_transcript_path}")
    print(f"obsidian_note_path: {result.obsidian_note_path}")
    print(f"cleanup: {result.cleanup}")
    if result.dry_run and result.cleanup_plan:
        print("cleanup_plan:")
        for item in result.cleanup_plan:
            print(f"  - {item}")
    elif result.cleanup_removed:
        print("cleanup_removed:")
        for path in result.cleanup_removed:
            print(f"  - {path}")
    else:
        print("cleanup_removed: []")
    if result.cleanup_skipped:
        print("cleanup_skipped:")
        for item in result.cleanup_skipped:
            print(f"  - {item}")
    else:
        print("cleanup_skipped: []")


def _display_source(source: str, limit: int = 90) -> str:
    parsed = urlparse(source)
    cleaned = parsed._replace(query="", fragment="").geturl() if parsed.scheme else source
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "course"


def _excerpt(text: str, limit: int = 500) -> str:
    return text[-limit:] if len(text) > limit else text


if __name__ == "__main__":
    raise SystemExit(main())
