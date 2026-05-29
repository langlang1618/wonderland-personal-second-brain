"""Pipeline runtime contracts.

This module defines orchestration data models and protocol boundaries for the
pipeline runtime. It intentionally contains no business stage implementation,
queue integration, async scheduler, or persistence side effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Protocol, TypeAlias

from ai_knowledge_pipeline.core.source import MetadataMap, SourceId


JobId: TypeAlias = str
TaskId: TypeAlias = str
RunId: TypeAlias = str
StageId: TypeAlias = str
StepId: TypeAlias = str
WorkerId: TypeAlias = str
CorrelationId: TypeAlias = str
ArtifactId: TypeAlias = str
EventId: TypeAlias = str
PipelineManifestVersion: TypeAlias = str
RuntimePayload: TypeAlias = Mapping[str, Any]


class PipelineStageKind(StrEnum):
    """Canonical pipeline stage names."""

    SOURCES = "sources"
    DOWNLOAD = "download"
    CHUNKING = "chunking"
    TRANSCRIPTION = "transcription"
    CLEANING = "cleaning"
    MARKDOWN = "markdown"
    OBSIDIAN = "obsidian"


class StageExecutionMode(StrEnum):
    """How a stage may be executed by a runtime."""

    SYNC = "sync"
    ASYNC = "async"
    QUEUED = "queued"
    AGENT = "agent"


class PipelineRunStatus(StrEnum):
    """Lifecycle state for a pipeline run."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskStatus(StrEnum):
    """Lifecycle state for an executable task."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


class StepOutcome(StrEnum):
    """Result classification for one stage execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    RETRYABLE_FAILURE = "retryable_failure"


class PipelineEventType(StrEnum):
    """Events emitted by the runtime boundary."""

    JOB_CREATED = "job_created"
    RUN_STARTED = "run_started"
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_RETRY_SCHEDULED = "task_retry_scheduled"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ARTIFACT_RECORDED = "artifact_recorded"
    RUN_PAUSED = "run_paused"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class PipelineErrorCode(StrEnum):
    """Stable runtime error codes."""

    STAGE_NOT_FOUND = "stage_not_found"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    DEPENDENCY_NOT_READY = "dependency_not_ready"
    STAGE_CONTRACT_VIOLATION = "stage_contract_violation"
    RETRY_EXHAUSTED = "retry_exhausted"
    EXECUTION_TIMEOUT = "execution_timeout"
    WORKER_UNAVAILABLE = "worker_unavailable"
    MANIFEST_PERSISTENCE_FAILED = "manifest_persistence_failed"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(StrEnum):
    """Severity levels for runtime errors."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class RetryBackoffStrategy(StrEnum):
    """Retry delay strategy."""

    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


class RetryDecision(StrEnum):
    """Runtime decision after a failed step."""

    DO_NOT_RETRY = "do_not_retry"
    RETRY_NOW = "retry_now"
    RETRY_LATER = "retry_later"
    ESCALATE = "escalate"


class LogLevel(StrEnum):
    """Logging levels used by runtime events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ArtifactKind(StrEnum):
    """Kinds of artifacts produced by stages."""

    SOURCE_MANIFEST = "source_manifest"
    MEDIA = "media"
    CHUNK = "chunk"
    RAW_TRANSCRIPT = "raw_transcript"
    CLEAN_TRANSCRIPT = "clean_transcript"
    MARKDOWN = "markdown"
    OBSIDIAN_NOTE = "obsidian_note"
    RUNTIME_MANIFEST = "runtime_manifest"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry strategy for a stage or task."""

    max_attempts: int = 1
    backoff: RetryBackoffStrategy = RetryBackoffStrategy.NONE
    initial_delay_seconds: float = 0
    max_delay_seconds: float | None = None
    retryable_error_codes: tuple[PipelineErrorCode, ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineError:
    """Structured runtime error propagated across orchestration boundaries."""

    code: PipelineErrorCode
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    stage_id: StageId | None = None
    task_id: TaskId | None = None
    cause: str | None = None
    details: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeArtifact:
    """Reference to an artifact produced or consumed by a task."""

    artifact_id: ArtifactId
    kind: ArtifactKind
    uri: str
    path: Path | None = None
    source_id: SourceId | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineStageSpec:
    """Static definition of one pipeline stage."""

    stage_id: StageId
    kind: PipelineStageKind
    name: str
    version: str = "v1"
    depends_on: tuple[StageId, ...] = ()
    execution_mode: StageExecutionMode = StageExecutionMode.SYNC
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    input_contract: str | None = None
    output_contract: str | None = None
    tags: tuple[str, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineJob:
    """User-submitted unit of work."""

    job_id: JobId
    source_ids: tuple[SourceId, ...]
    requested_stages: tuple[StageId, ...]
    config_profile: str = "default"
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineTask:
    """Executable stage unit derived from a job."""

    task_id: TaskId
    job_id: JobId
    run_id: RunId
    stage_id: StageId
    source_id: SourceId | None = None
    status: TaskStatus = TaskStatus.PENDING
    attempt: int = 0
    max_attempts: int = 1
    depends_on: tuple[TaskId, ...] = ()
    assigned_worker: WorkerId | None = None
    input_artifacts: tuple[RuntimeArtifact, ...] = ()
    output_artifacts: tuple[RuntimeArtifact, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineState:
    """Serializable state snapshot for a pipeline run."""

    run_id: RunId
    job_id: JobId
    status: PipelineRunStatus
    tasks: Mapping[TaskId, PipelineTask] = field(default_factory=dict)
    completed_stage_ids: tuple[StageId, ...] = ()
    failed_task_ids: tuple[TaskId, ...] = ()
    artifacts: Mapping[ArtifactId, RuntimeArtifact] = field(default_factory=dict)
    errors: tuple[PipelineError, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Context passed to stage executors."""

    run_id: RunId
    job_id: JobId
    task_id: TaskId
    stage: PipelineStageSpec
    config_profile: str = "default"
    correlation_id: CorrelationId | None = None
    worker_id: WorkerId | None = None
    state: PipelineState | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StepResult:
    """Contract returned by one stage execution."""

    task_id: TaskId
    stage_id: StageId
    outcome: StepOutcome
    output_artifacts: tuple[RuntimeArtifact, ...] = ()
    state_patch: RuntimePayload = field(default_factory=dict)
    errors: tuple[PipelineError, ...] = ()
    events: tuple["PipelineEvent", ...] = ()
    retry_after_seconds: float | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetryEvaluation:
    """Decision produced after inspecting a failed step result."""

    decision: RetryDecision
    next_attempt: int
    delay_seconds: float | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class LogRecord:
    """Structured log record emitted by runtime components."""

    level: LogLevel
    message: str
    run_id: RunId | None = None
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId | None = None
    correlation_id: CorrelationId | None = None
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """Append-only event describing a runtime transition."""

    event_id: EventId
    event_type: PipelineEventType
    run_id: RunId
    job_id: JobId | None = None
    task_id: TaskId | None = None
    stage_id: StageId | None = None
    payload: RuntimePayload = field(default_factory=dict)
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineManifest:
    """Serializable manifest for replaying or resuming a pipeline run."""

    manifest_version: PipelineManifestVersion
    run_id: RunId
    job: PipelineJob
    stages: tuple[PipelineStageSpec, ...]
    state: PipelineState
    events: tuple[PipelineEvent, ...] = ()
    artifacts: tuple[RuntimeArtifact, ...] = ()
    metadata: MetadataMap = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineRuntimeConfig:
    """Configuration knobs for runtime orchestration."""

    manifest_dir: Path = Path("data/raw/pipeline-runs")
    event_log_dir: Path = Path("data/raw/pipeline-events")
    default_retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    max_concurrent_tasks: int = 1
    enable_event_log: bool = True
    enable_resume: bool = True


class PipelineStageExecutor(Protocol):
    """Boundary implemented by each concrete stage runner."""

    stage: PipelineStageSpec

    def execute(self, context: ExecutionContext) -> StepResult:
        """Run one stage task and return a structured result."""


class PipelineStateStore(Protocol):
    """Persistence boundary for runtime state snapshots."""

    def save(self, state: PipelineState) -> Path:
        """Persist a state snapshot and return its path."""

    def load(self, run_id: RunId) -> PipelineState:
        """Load a state snapshot by run id."""


class PipelineEventSink(Protocol):
    """Append-only event boundary."""

    def emit(self, event: PipelineEvent) -> None:
        """Record a runtime event."""


class PipelineLogger(Protocol):
    """Structured logging boundary."""

    def log(self, record: LogRecord) -> None:
        """Record a structured log event."""


class RetryStrategy(Protocol):
    """Retry policy evaluator."""

    def evaluate(
        self,
        task: PipelineTask,
        result: StepResult,
        policy: RetryPolicy,
    ) -> RetryEvaluation:
        """Return the retry decision for a failed step."""


class PipelineManifestStore(Protocol):
    """Persistence boundary for pipeline manifests."""

    def save(self, manifest: PipelineManifest) -> Path:
        """Persist a manifest snapshot."""

    def load(self, run_id: RunId) -> PipelineManifest:
        """Load a manifest snapshot by run id."""


class PipelineRuntime(Protocol):
    """Top-level orchestration boundary."""

    def submit(self, job: PipelineJob) -> PipelineManifest:
        """Create a run manifest from a job."""

    def resume(self, run_id: RunId) -> PipelineManifest:
        """Resume a persisted run manifest."""

    def step(self, run_id: RunId) -> PipelineManifest:
        """Advance a run by one scheduler step."""


__all__ = [
    "ArtifactId",
    "ArtifactKind",
    "CorrelationId",
    "ErrorSeverity",
    "EventId",
    "ExecutionContext",
    "JobId",
    "LogLevel",
    "LogRecord",
    "PipelineError",
    "PipelineErrorCode",
    "PipelineEvent",
    "PipelineEventSink",
    "PipelineEventType",
    "PipelineJob",
    "PipelineLogger",
    "PipelineManifest",
    "PipelineManifestStore",
    "PipelineManifestVersion",
    "PipelineRunStatus",
    "PipelineRuntime",
    "PipelineRuntimeConfig",
    "PipelineStageExecutor",
    "PipelineStageKind",
    "PipelineStageSpec",
    "PipelineState",
    "PipelineStateStore",
    "PipelineTask",
    "RetryBackoffStrategy",
    "RetryDecision",
    "RetryEvaluation",
    "RetryPolicy",
    "RetryStrategy",
    "RunId",
    "RuntimeArtifact",
    "RuntimePayload",
    "StageExecutionMode",
    "StageId",
    "StepId",
    "StepOutcome",
    "StepResult",
    "TaskId",
    "TaskStatus",
    "WorkerId",
]
