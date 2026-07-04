"""Download m3u8 audio and split it into local chunks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Protocol, Sequence
from urllib.parse import urlparse

from ai_knowledge_pipeline.infra.runtime_logging import (
    STAGE_AUDIO_CHUNKING,
    STAGE_AUDIO_EXTRACTION,
    RuntimeLogger,
    create_runtime_logger,
)
from ai_knowledge_pipeline.modules.chunking.runner import SubprocessFfmpegRunner
from ai_knowledge_pipeline.modules.chunking.types import (
    ChunkProcessResult,
    MediaChunkingConfig,
)
from ai_knowledge_pipeline.modules.download.runner import SubprocessYtDlpRunner
from ai_knowledge_pipeline.modules.download.types import (
    DownloadProcessResult,
    MediaDownloadConfig,
)


class MediaIngestionStatus(StrEnum):
    """Status for one media ingestion item."""

    PLANNED = "planned"
    MATERIALIZED = "materialized"
    SKIPPED = "skipped"
    FAILED = "failed"


class YtDlpRunner(Protocol):
    """Minimal yt-dlp runner protocol."""

    def run(
        self,
        command: tuple[str, ...],
        config: MediaDownloadConfig,
    ) -> DownloadProcessResult: ...


class FfmpegRunner(Protocol):
    """Minimal ffmpeg runner protocol."""

    def run(
        self,
        command: tuple[str, ...],
        config: MediaChunkingConfig,
    ) -> ChunkProcessResult: ...


@dataclass(frozen=True, slots=True)
class MediaIngestionRequest:
    """Input for one media ingestion batch."""

    urls: tuple[str, ...]
    output_dir: Path = Path("data/media_ingestion")
    title: str | None = None
    audio_format: str = "mp3"
    chunk_minutes: int = 30
    dry_run: bool = False
    skip_existing: bool = False


@dataclass(frozen=True, slots=True)
class MediaIngestionPlan:
    """Filesystem and command plan for one URL."""

    source_url: str
    title: str
    course_dir: Path
    raw_audio_dir: Path
    chunks_dir: Path
    manifest_path: Path
    downloaded_audio_path: Path
    chunk_pattern: Path
    download_command: tuple[str, ...]
    chunk_command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediaIngestionItemResult:
    """Result for one URL ingestion."""

    index: int
    plan: MediaIngestionPlan
    status: MediaIngestionStatus
    chunk_paths: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def is_success(self) -> bool:
        return self.status in {
            MediaIngestionStatus.PLANNED,
            MediaIngestionStatus.MATERIALIZED,
            MediaIngestionStatus.SKIPPED,
        }


@dataclass(frozen=True, slots=True)
class MediaIngestionBatchResult:
    """Summary for a media ingestion batch."""

    items: tuple[MediaIngestionItemResult, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def success(self) -> int:
        return sum(
            1 for item in self.items if item.status is MediaIngestionStatus.MATERIALIZED
        )

    @property
    def failed(self) -> int:
        return sum(1 for item in self.items if item.status is MediaIngestionStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(
            1
            for item in self.items
            if item.status in {MediaIngestionStatus.SKIPPED, MediaIngestionStatus.PLANNED}
        )


def run_media_ingestion(
    request: MediaIngestionRequest,
    *,
    ytdlp_runner: YtDlpRunner | None = None,
    ffmpeg_runner: FfmpegRunner | None = None,
    logger: RuntimeLogger | None = None,
) -> MediaIngestionBatchResult:
    """Run media ingestion for one or more m3u8 URLs."""

    runtime_logger = logger or create_runtime_logger()
    ytdlp_runner = ytdlp_runner or SubprocessYtDlpRunner()
    ffmpeg_runner = ffmpeg_runner or SubprocessFfmpegRunner()
    items: list[MediaIngestionItemResult] = []
    for index, url in enumerate(request.urls, start=1):
        plan = _build_plan(request, url, index)
        runtime_logger.info(f"Media item {index} / {len(request.urls)}: {plan.title}")
        if request.dry_run:
            runtime_logger.info(f"dry-run: planned media ingestion for {plan.title}")
            item = MediaIngestionItemResult(
                index=index,
                plan=plan,
                status=MediaIngestionStatus.PLANNED,
            )
            _write_manifest(plan, item)
            items.append(item)
            continue

        if request.skip_existing and _has_existing_outputs(plan, request.audio_format):
            runtime_logger.info(f"skip_existing: using existing media outputs: {plan.course_dir}")
            item = MediaIngestionItemResult(
                index=index,
                plan=plan,
                status=MediaIngestionStatus.SKIPPED,
                chunk_paths=_chunk_paths(plan, request.audio_format),
            )
            _write_manifest(plan, item)
            items.append(item)
            continue

        item = _materialize_item(
            index=index,
            plan=plan,
            request=request,
            ytdlp_runner=ytdlp_runner,
            ffmpeg_runner=ffmpeg_runner,
            logger=runtime_logger,
        )
        _write_manifest(plan, item)
        items.append(item)
    return MediaIngestionBatchResult(items=tuple(items))


def load_urls(*, m3u8: str | None, url_file: Path | None) -> tuple[str, ...]:
    """Load URLs from direct input and/or a text file."""

    urls: list[str] = []
    if m3u8:
        urls.append(m3u8.strip())
    if url_file is not None:
        urls.extend(
            line.strip()
            for line in url_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    return tuple(url for url in urls if url)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    urls = load_urls(
        m3u8=args.m3u8,
        url_file=Path(args.url_file) if args.url_file else None,
    )
    if not urls:
        print("Error: provide --m3u8 or --url-file.", file=sys.stderr)
        return 2

    result = run_media_ingestion(
        MediaIngestionRequest(
            urls=urls,
            output_dir=Path(args.output_dir),
            title=args.title,
            audio_format=args.audio_format,
            chunk_minutes=args.chunk_minutes,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
        )
    )
    _print_result(result)
    return 0 if result.failed == 0 else 1


def _materialize_item(
    *,
    index: int,
    plan: MediaIngestionPlan,
    request: MediaIngestionRequest,
    ytdlp_runner: YtDlpRunner,
    ffmpeg_runner: FfmpegRunner,
    logger: RuntimeLogger,
) -> MediaIngestionItemResult:
    plan.raw_audio_dir.mkdir(parents=True, exist_ok=True)
    plan.chunks_dir.mkdir(parents=True, exist_ok=True)

    with logger.stage(STAGE_AUDIO_EXTRACTION):
        download_result = ytdlp_runner.run(
            plan.download_command,
            MediaDownloadConfig(ytdlp_binary=plan.download_command[0]),
        )
    if download_result.returncode != 0:
        logger.error(f"{STAGE_AUDIO_EXTRACTION} failed: {_excerpt(download_result.output.stderr)}")
        return MediaIngestionItemResult(
            index=index,
            plan=plan,
            status=MediaIngestionStatus.FAILED,
            errors=(f"yt-dlp failed: {_excerpt(download_result.output.stderr)}",),
        )

    with logger.stage(STAGE_AUDIO_CHUNKING) as stage:
        chunk_result = ffmpeg_runner.run(
            plan.chunk_command,
            MediaChunkingConfig(ffmpeg_binary=plan.chunk_command[0]),
        )
        chunk_paths = _chunk_paths(plan, request.audio_format)
        stage.progress(f"chunks: {len(chunk_paths)}")
    if chunk_result.returncode != 0:
        logger.error(f"{STAGE_AUDIO_CHUNKING} failed: {_excerpt(chunk_result.output.stderr)}")
        return MediaIngestionItemResult(
            index=index,
            plan=plan,
            status=MediaIngestionStatus.FAILED,
            errors=(f"ffmpeg failed: {_excerpt(chunk_result.output.stderr)}",),
        )

    return MediaIngestionItemResult(
        index=index,
        plan=plan,
        status=MediaIngestionStatus.MATERIALIZED,
        chunk_paths=chunk_paths,
    )


def _build_plan(
    request: MediaIngestionRequest,
    url: str,
    index: int,
) -> MediaIngestionPlan:
    title = _title_for(request, url, index)
    course_dir = request.output_dir / _slugify(title)
    raw_audio_dir = course_dir / "raw_audio"
    chunks_dir = course_dir / "chunks"
    audio_path = raw_audio_dir / f"course.{request.audio_format}"
    chunk_pattern = chunks_dir / f"chunk_%03d.{request.audio_format}"
    download_template = raw_audio_dir / "course.%(ext)s"
    download_command = (
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        request.audio_format,
        "--output",
        str(download_template),
        url,
    )
    chunk_seconds = request.chunk_minutes * 60
    chunk_command = (
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-segment_start_number",
        "1",
        "-c",
        "copy",
        str(chunk_pattern),
    )
    return MediaIngestionPlan(
        source_url=url,
        title=title,
        course_dir=course_dir,
        raw_audio_dir=raw_audio_dir,
        chunks_dir=chunks_dir,
        manifest_path=course_dir / "manifest.json",
        downloaded_audio_path=audio_path,
        chunk_pattern=chunk_pattern,
        download_command=download_command,
        chunk_command=chunk_command,
    )


def _write_manifest(plan: MediaIngestionPlan, item: MediaIngestionItemResult) -> None:
    plan.course_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_url": plan.source_url,
        "title": plan.title,
        "downloaded_audio_path": str(plan.downloaded_audio_path),
        "chunk_paths": [str(path) for path in item.chunk_paths],
        "chunk_minutes": _chunk_minutes_from_command(plan.chunk_command),
        "audio_format": plan.downloaded_audio_path.suffix.lstrip("."),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": item.status.value,
        "errors": list(item.errors),
    }
    plan.manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _has_existing_outputs(plan: MediaIngestionPlan, audio_format: str) -> bool:
    return plan.downloaded_audio_path.exists() and bool(_chunk_paths(plan, audio_format))


def _chunk_paths(plan: MediaIngestionPlan, audio_format: str) -> tuple[Path, ...]:
    if not plan.chunks_dir.exists():
        return ()
    return tuple(sorted(plan.chunks_dir.glob(f"chunk_*.{audio_format}")))


def _title_for(request: MediaIngestionRequest, url: str, index: int) -> str:
    if request.title:
        return request.title if len(request.urls) == 1 else f"{request.title} {index:03d}"
    parsed = urlparse(url)
    stem = Path(parsed.path).stem
    return stem or f"course_{index:03d}"


def _chunk_minutes_from_command(command: tuple[str, ...]) -> int:
    try:
        seconds = int(command[command.index("-segment_time") + 1])
    except (ValueError, IndexError):
        return 0
    return seconds // 60


def _print_result(result: MediaIngestionBatchResult) -> None:
    for item in result.items:
        print(
            f"[{item.index:03d}] {_display_url(item.plan.source_url)} -> "
            f"{item.plan.downloaded_audio_path} {item.status.value}"
        )
        if item.errors:
            print(f"  error: {item.errors[0]}")
        elif item.chunk_paths:
            print(f"  chunks: {len(item.chunk_paths)}")
    print("Media ingestion summary:")
    print(f"total: {result.total}")
    print(f"success: {result.success}")
    print(f"failed: {result.failed}")
    print(f"skipped: {result.skipped}")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download m3u8 audio and split it.")
    parser.add_argument("--m3u8", help="Single m3u8 URL.")
    parser.add_argument("--url-file", help="Text file containing one m3u8 URL per line.")
    parser.add_argument("--output-dir", default="data/media_ingestion")
    parser.add_argument("--title", help="Course title or title prefix for multiple URLs.")
    parser.add_argument("--audio-format", default="mp3")
    parser.add_argument("--chunk-minutes", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args(argv)


def _display_url(url: str, limit: int = 90) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(query="", fragment="").geturl()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "untitled"


def _excerpt(text: str, limit: int = 500) -> str:
    return text[-limit:] if len(text) > limit else text


if __name__ == "__main__":
    raise SystemExit(main())
