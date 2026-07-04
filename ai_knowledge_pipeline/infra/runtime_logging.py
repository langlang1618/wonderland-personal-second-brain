"""Lightweight runtime logging for local pipeline orchestration."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter
from typing import Iterator, Sequence, TextIO


STAGE_PROFILE_LOADING = "Profile Loading"
STAGE_AUDIO_EXTRACTION = "Audio Extraction"
STAGE_AUDIO_CHUNKING = "Audio Chunking"
STAGE_WHISPER_TRANSCRIPTION = "Whisper Transcription"
STAGE_DEEPSEEK_CLEANING = "DeepSeek Cleaning"
STAGE_MARKDOWN_GENERATION = "Markdown Generation"
STAGE_SAVE_OUTPUT = "Save Output"


class RuntimeMetricStatus(StrEnum):
    """Status for a recorded runtime metric."""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RuntimeMetric:
    """One stage or chunk runtime measurement."""

    stage_name: str
    elapsed_seconds: float
    status: RuntimeMetricStatus
    chunk_index: int | None = None
    total_chunks: int | None = None
    chunk_name: str | None = None


@dataclass(slots=True)
class RuntimeMetricsCollector:
    """In-memory runtime metrics for one pipeline execution."""

    metrics: list[RuntimeMetric] = field(default_factory=list)

    def record(self, metric: RuntimeMetric) -> None:
        self.metrics.append(metric)

    def all(self) -> tuple[RuntimeMetric, ...]:
        return tuple(self.metrics)

    def total_runtime_seconds(self) -> float:
        return sum(
            metric.elapsed_seconds
            for metric in self.metrics
            if metric.chunk_index is None
        )

    def by_stage(self, stage_name: str) -> tuple[RuntimeMetric, ...]:
        return tuple(metric for metric in self.metrics if metric.stage_name == stage_name)

    def stage_metrics(self) -> tuple[RuntimeMetric, ...]:
        return tuple(metric for metric in self.metrics if metric.chunk_index is None)

    def chunk_metrics(self, stage_name: str | None = None) -> tuple[RuntimeMetric, ...]:
        return tuple(
            metric
            for metric in self.metrics
            if metric.chunk_index is not None
            and (stage_name is None or metric.stage_name == stage_name)
        )


@dataclass(frozen=True, slots=True)
class RuntimeLogger:
    """Small stdout logger with consistent pipeline prefixes."""

    stream: TextIO = sys.stdout
    metrics: RuntimeMetricsCollector = field(default_factory=RuntimeMetricsCollector)

    def info(self, message: str) -> None:
        self._emit("INFO", message)

    def progress(self, message: str) -> None:
        self._emit("PROGRESS", message)

    def success(self, message: str) -> None:
        self._emit("SUCCESS", message)

    def warning(self, message: str) -> None:
        self._emit("WARNING", message)

    def error(self, message: str) -> None:
        self._emit("ERROR", message)

    @contextmanager
    def stage(self, name: str) -> Iterator["RuntimeStage"]:
        """Log start and finish for a named stage."""

        stage = RuntimeStage(name=name, logger=self, started_at=perf_counter())
        self.info(f"{name} started")
        try:
            yield stage
        except Exception as exc:
            elapsed = stage.elapsed_seconds()
            self.metrics.record(
                RuntimeMetric(
                    stage_name=name,
                    elapsed_seconds=elapsed,
                    status=RuntimeMetricStatus.ERROR,
                )
            )
            self.error(f"{name} failed | elapsed: {_format_elapsed(elapsed)} | {exc}")
            raise
        else:
            elapsed = stage.elapsed_seconds()
            self.metrics.record(
                RuntimeMetric(
                    stage_name=name,
                    elapsed_seconds=elapsed,
                    status=RuntimeMetricStatus.SUCCESS,
                )
            )
            self.success(f"{name} finished | elapsed: {_format_elapsed(elapsed)}")

    @contextmanager
    def chunk(
        self,
        stage_name: str,
        *,
        chunk_index: int,
        total_chunks: int,
        chunk_name: str | None = None,
    ) -> Iterator["RuntimeChunk"]:
        """Log and record timing for one chunk of work."""

        chunk = RuntimeChunk(
            stage_name=stage_name,
            logger=self,
            started_at=perf_counter(),
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            chunk_name=chunk_name,
        )
        self.progress(f"{stage_name} | {chunk.label()} started")
        try:
            yield chunk
        except Exception as exc:
            elapsed = chunk.elapsed_seconds()
            self.metrics.record(chunk.metric(RuntimeMetricStatus.ERROR, elapsed))
            self.error(
                f"{stage_name} | {chunk.label()} failed | "
                f"elapsed: {_format_elapsed(elapsed)} | {exc}"
            )
            raise
        else:
            elapsed = chunk.elapsed_seconds()
            self.metrics.record(chunk.metric(RuntimeMetricStatus.SUCCESS, elapsed))
            self.success(
                f"{stage_name} | {chunk.label()} finished | "
                f"elapsed: {_format_elapsed(elapsed)}"
            )

    def _emit(self, level: str, message: str) -> None:
        print(f"[{level}] {message}", file=self.stream, flush=True)

    def recorded_metrics(self) -> tuple[RuntimeMetric, ...]:
        return self.metrics.all()


@dataclass(frozen=True, slots=True)
class RuntimeStage:
    """A running stage that can emit progress with elapsed time."""

    name: str
    logger: RuntimeLogger
    started_at: float

    def progress(self, message: str) -> None:
        self.logger.progress(
            f"{self.name} | {message} | elapsed: {_format_elapsed(self.elapsed_seconds())}"
        )

    def elapsed_seconds(self) -> float:
        return perf_counter() - self.started_at


@dataclass(frozen=True, slots=True)
class RuntimeChunk:
    """A timed unit of chunk-based work."""

    stage_name: str
    logger: RuntimeLogger
    started_at: float
    chunk_index: int
    total_chunks: int
    chunk_name: str | None = None

    def label(self) -> str:
        suffix = f": {self.chunk_name}" if self.chunk_name else ""
        return f"Chunk {self.chunk_index} / {self.total_chunks}{suffix}"

    def elapsed_seconds(self) -> float:
        return perf_counter() - self.started_at

    def metric(
        self,
        status: RuntimeMetricStatus,
        elapsed_seconds: float | None = None,
    ) -> RuntimeMetric:
        return RuntimeMetric(
            stage_name=self.stage_name,
            elapsed_seconds=self.elapsed_seconds()
            if elapsed_seconds is None
            else elapsed_seconds,
            status=status,
            chunk_index=self.chunk_index,
            total_chunks=self.total_chunks,
            chunk_name=self.chunk_name,
        )


def create_runtime_logger(stream: TextIO | None = None) -> RuntimeLogger:
    """Create the default runtime logger."""

    return RuntimeLogger(stream=stream or sys.stdout)


def _format_elapsed(seconds: float) -> str:
    if seconds >= 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining = int(seconds % 60)
        return f"{hours}h{minutes:02d}m{remaining:02d}s"
    if seconds >= 60:
        minutes = int(seconds // 60)
        remaining = int(seconds % 60)
        return f"{minutes}m{remaining:02d}s"
    return f"{seconds:.1f} s"


def render_pipeline_summary(
    metrics: RuntimeMetricsCollector,
    *,
    profile: str | None = None,
    course: str | None = None,
    audio_length: str | None = None,
    chunks: int | None = None,
) -> str:
    """Render a copy-friendly console summary from collected runtime metrics."""

    line = "=" * 54
    divider = "-" * 54
    rows: list[str] = [
        line,
        "Wonderland Pipeline Summary",
        line,
        "Profile",
        profile or "Unknown",
        "",
        "Course",
        course or "Unknown",
        "",
        "Audio Length",
        audio_length or "Unknown",
        "",
        "Chunks",
        str(chunks if chunks is not None else _chunk_count(metrics)),
        divider,
        "Stage Metrics",
        divider,
    ]
    stage_metrics = metrics.stage_metrics()
    if stage_metrics:
        rows.extend(_metric_rows(stage_metrics))
    else:
        rows.append("No stage metrics recorded")

    rows.extend([divider, "Whisper Metrics", divider])
    whisper_metrics = metrics.chunk_metrics(STAGE_WHISPER_TRANSCRIPTION)
    if whisper_metrics:
        rows.extend(_chunk_rows(whisper_metrics))
    else:
        rows.append("No Whisper chunk metrics recorded")

    rows.extend(
        [
            divider,
            "Pipeline Runtime",
            divider,
            "TOTAL",
            _format_elapsed(metrics.total_runtime_seconds()),
            line,
        ]
    )
    return "\n".join(rows)


def print_pipeline_summary(
    logger: RuntimeLogger,
    *,
    profile: str | None = None,
    course: str | None = None,
    audio_length: str | None = None,
    chunks: int | None = None,
) -> None:
    """Print a pipeline runtime summary to the logger stream."""

    print(
        render_pipeline_summary(
            logger.metrics,
            profile=profile,
            course=course,
            audio_length=audio_length,
            chunks=chunks,
        ),
        file=logger.stream,
        flush=True,
    )


def _metric_rows(metrics: Sequence[RuntimeMetric]) -> list[str]:
    return [
        f"{metric.stage_name:<24}{_format_elapsed(metric.elapsed_seconds):>12}"
        for metric in metrics
    ]


def _chunk_rows(metrics: Sequence[RuntimeMetric]) -> list[str]:
    ordered = sorted(metrics, key=lambda metric: metric.chunk_index or 0)
    return [
        f"Chunk {metric.chunk_index:<6}{_format_elapsed(metric.elapsed_seconds):>12}"
        for metric in ordered
    ]


def _chunk_count(metrics: RuntimeMetricsCollector) -> int:
    chunk_totals = [
        metric.total_chunks
        for metric in metrics.chunk_metrics(STAGE_WHISPER_TRANSCRIPTION)
        if metric.total_chunks is not None
    ]
    return max(chunk_totals) if chunk_totals else 0


__all__ = [
    "RuntimeChunk",
    "RuntimeLogger",
    "RuntimeMetric",
    "RuntimeMetricStatus",
    "RuntimeMetricsCollector",
    "RuntimeStage",
    "STAGE_AUDIO_CHUNKING",
    "STAGE_AUDIO_EXTRACTION",
    "STAGE_DEEPSEEK_CLEANING",
    "STAGE_MARKDOWN_GENERATION",
    "STAGE_PROFILE_LOADING",
    "STAGE_SAVE_OUTPUT",
    "STAGE_WHISPER_TRANSCRIPTION",
    "create_runtime_logger",
    "print_pipeline_summary",
    "render_pipeline_summary",
]
