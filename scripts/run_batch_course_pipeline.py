"""Run multiple local course transcripts through the knowledge pipeline."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Sequence

from ai_knowledge_pipeline.modules.cleaning import (
    KnowledgeProfileName,
    TranscriptCleaningProvider,
)
from scripts.run_real_course_pipeline import (
    DEFAULT_DEEPSEEK_MODEL,
    RealCoursePipelineError,
    RealCoursePipelineRequest,
    _load_value,
    _parse_tags,
    _read_env_file,
    run_real_course_pipeline,
)


SUPPORTED_TRANSCRIPT_SUFFIXES = (".txt", ".srt")
DEFAULT_OBSIDIAN_ROOT_DIR = "AI Knowledge Pipeline"


class BatchItemStatus(StrEnum):
    """Status for one transcript in a batch run."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"


@dataclass(frozen=True, slots=True)
class BatchCoursePipelineRequest:
    """Input for a batch course transcript run."""

    input_dir: Path
    obsidian_vault_path: Path
    profile: KnowledgeProfileName = KnowledgeProfileName.AI
    tags: tuple[str, ...] = ()
    title_prefix: str | None = None
    model: str = DEFAULT_DEEPSEEK_MODEL
    limit: int | None = None
    dry_run: bool = False
    skip_existing: bool = False
    env_path: Path = Path(".env")


@dataclass(frozen=True, slots=True)
class BatchCourseItemResult:
    """Result for one transcript in a batch run."""

    index: int
    transcript_path: Path
    title: str
    status: BatchItemStatus
    note_path: Path | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class BatchCoursePipelineResult:
    """Summary of a batch course transcript run."""

    items: tuple[BatchCourseItemResult, ...]

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def success(self) -> int:
        return sum(1 for item in self.items if item.status is BatchItemStatus.SUCCESS)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.items if item.status is BatchItemStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(
            1
            for item in self.items
            if item.status in {BatchItemStatus.SKIPPED, BatchItemStatus.DRY_RUN}
        )

    @property
    def generated_note_paths(self) -> tuple[Path, ...]:
        return tuple(
            item.note_path
            for item in self.items
            if item.status is BatchItemStatus.SUCCESS and item.note_path is not None
        )


class BatchCoursePipelineError(RuntimeError):
    """Raised when batch setup cannot start."""


def run_batch_course_pipeline(
    request: BatchCoursePipelineRequest,
    cleaning_provider: TranscriptCleaningProvider | None = None,
) -> BatchCoursePipelineResult:
    """Run all selected transcripts, continuing after per-file failures."""

    transcript_paths = scan_transcript_files(request.input_dir, limit=request.limit)
    results: list[BatchCourseItemResult] = []
    for index, transcript_path in enumerate(transcript_paths, start=1):
        title = _title_for(transcript_path, request.title_prefix, index)
        expected_path = _expected_note_path(
            request.obsidian_vault_path,
            title=title,
            tags=request.tags,
        )
        if request.dry_run:
            results.append(
                BatchCourseItemResult(
                    index=index,
                    transcript_path=transcript_path,
                    title=title,
                    status=BatchItemStatus.DRY_RUN,
                    note_path=expected_path,
                    message="dry-run",
                )
            )
            continue
        if request.skip_existing and expected_path.exists():
            results.append(
                BatchCourseItemResult(
                    index=index,
                    transcript_path=transcript_path,
                    title=title,
                    status=BatchItemStatus.SKIPPED,
                    note_path=expected_path,
                    message="existing note skipped",
                )
            )
            continue

        try:
            single_result = run_real_course_pipeline(
                RealCoursePipelineRequest(
                    local_transcript_path=transcript_path,
                    obsidian_vault_path=request.obsidian_vault_path,
                    title=title,
                    tags=request.tags,
                    model=request.model,
                    profile=request.profile,
                    env_path=request.env_path,
                    run_id=f"batch-course-run-{index:03d}",
                    job_id="batch-course-job",
                ),
                cleaning_provider=cleaning_provider,
            )
        except RealCoursePipelineError as exc:
            results.append(
                BatchCourseItemResult(
                    index=index,
                    transcript_path=transcript_path,
                    title=title,
                    status=BatchItemStatus.FAILED,
                    message=str(exc),
                )
            )
            continue

        results.append(
            BatchCourseItemResult(
                index=index,
                transcript_path=transcript_path,
                title=title,
                status=BatchItemStatus.SUCCESS,
                note_path=single_result.obsidian_note_path,
                message="ok",
            )
        )
    return BatchCoursePipelineResult(items=tuple(results))


def scan_transcript_files(input_dir: Path, limit: int | None = None) -> tuple[Path, ...]:
    """Scan supported transcript files in natural filename order."""

    if not input_dir.exists() or not input_dir.is_dir():
        raise BatchCoursePipelineError(f"Input directory does not exist: {input_dir}")
    files = tuple(
        sorted(
            (
                path
                for path in input_dir.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_TRANSCRIPT_SUFFIXES
            ),
            key=lambda path: _natural_sort_key(path.name),
        )
    )
    return files[:limit] if limit is not None else files


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    env_values = _read_env_file(Path(".env"))
    vault = args.vault or _load_value("OBSIDIAN_VAULT_PATH", env_values)
    model = args.model or _load_value("DEEPSEEK_MODEL", env_values) or DEFAULT_DEEPSEEK_MODEL
    if vault is None:
        print(
            "Error: Obsidian vault path is required. Pass --vault or set OBSIDIAN_VAULT_PATH.",
            file=sys.stderr,
        )
        return 2

    request = BatchCoursePipelineRequest(
        input_dir=Path(args.input_dir),
        obsidian_vault_path=Path(vault),
        profile=KnowledgeProfileName(args.profile),
        tags=_parse_tags(args.tags),
        title_prefix=args.title_prefix,
        model=model,
        limit=args.limit,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
    )
    try:
        result = run_batch_course_pipeline(request)
    except BatchCoursePipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_result(result)
    return 0 if result.failed == 0 else 1


def _print_result(result: BatchCoursePipelineResult) -> None:
    for item in result.items:
        note = str(item.note_path) if item.note_path is not None else "-"
        print(
            f"[{item.index:03d}] {item.transcript_path} -> {note} "
            f"{item.status.value} {item.message}".rstrip()
        )
    print("Batch summary:")
    print(f"total: {result.total}")
    print(f"success: {result.success}")
    print(f"failed: {result.failed}")
    print(f"skipped: {result.skipped}")
    print("generated note paths:")
    for path in result.generated_note_paths:
        print(f"- {path}")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a directory of local course transcripts through the pipeline.",
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing .txt/.srt transcripts.")
    parser.add_argument("--vault", help="Obsidian vault path. Falls back to OBSIDIAN_VAULT_PATH.")
    parser.add_argument(
        "--profile",
        choices=tuple(profile.value for profile in KnowledgeProfileName),
        default=KnowledgeProfileName.AI.value,
        help="Knowledge profile used for every transcript.",
    )
    parser.add_argument("--tags", help="Comma-separated note tags.")
    parser.add_argument("--title-prefix", help="Prefix for generated note titles.")
    parser.add_argument("--model", help="DeepSeek model. Defaults to DEEPSEEK_MODEL.")
    parser.add_argument("--limit", type=int, help="Only process the first N files.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned files without processing.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip notes whose expected path already exists.")
    return parser.parse_args(argv)


def _title_for(path: Path, title_prefix: str | None, index: int) -> str:
    if title_prefix:
        return f"{title_prefix} {index:03d}"
    return path.stem


def _expected_note_path(vault_path: Path, *, title: str, tags: tuple[str, ...]) -> Path:
    category = tags[0] if tags else "uncategorized"
    return (
        vault_path
        / DEFAULT_OBSIDIAN_ROOT_DIR
        / _slugify(category)
        / f"{_slugify(title)}.md"
    )


def _natural_sort_key(value: str) -> tuple[int | str, ...]:
    parts = re.split(r"(\d+)", value)
    return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug.lower() or "untitled"


if __name__ == "__main__":
    raise SystemExit(main())
