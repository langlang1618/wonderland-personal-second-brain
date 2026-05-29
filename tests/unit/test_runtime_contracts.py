from pathlib import Path

from ai_knowledge_pipeline.core.runtime import (
    ArtifactKind,
    ErrorSeverity,
    PipelineError,
    PipelineErrorCode,
    PipelineEvent,
    PipelineEventType,
    PipelineJob,
    PipelineManifest,
    PipelineRunStatus,
    PipelineStageKind,
    PipelineStageSpec,
    PipelineState,
    PipelineTask,
    RetryBackoffStrategy,
    RetryDecision,
    RetryEvaluation,
    RetryPolicy,
    RuntimeArtifact,
    StepOutcome,
    StepResult,
    TaskStatus,
)


def test_stage_spec_can_model_pipeline_dependencies() -> None:
    download = PipelineStageSpec(
        stage_id="download",
        kind=PipelineStageKind.DOWNLOAD,
        name="Download media",
        depends_on=("sources",),
        retry_policy=RetryPolicy(
            max_attempts=3,
            backoff=RetryBackoffStrategy.EXPONENTIAL,
        ),
    )

    assert download.depends_on == ("sources",)
    assert download.retry_policy.max_attempts == 3


def test_step_result_carries_artifacts_and_errors() -> None:
    artifact = RuntimeArtifact(
        artifact_id="artifact_media_1",
        kind=ArtifactKind.MEDIA,
        uri="file://data/media/example.m4a",
        path=Path("data/media/example.m4a"),
        source_id="src_1",
    )
    error = PipelineError(
        code=PipelineErrorCode.EXECUTION_TIMEOUT,
        message="Stage timed out.",
        severity=ErrorSeverity.ERROR,
        stage_id="download",
        task_id="task_1",
    )

    result = StepResult(
        task_id="task_1",
        stage_id="download",
        outcome=StepOutcome.RETRYABLE_FAILURE,
        output_artifacts=(artifact,),
        errors=(error,),
        retry_after_seconds=30,
    )

    assert result.outcome is StepOutcome.RETRYABLE_FAILURE
    assert result.output_artifacts[0].source_id == "src_1"
    assert result.errors[0].code is PipelineErrorCode.EXECUTION_TIMEOUT


def test_pipeline_manifest_can_snapshot_run_state() -> None:
    job = PipelineJob(
        job_id="job_1",
        source_ids=("src_1",),
        requested_stages=("sources", "download"),
    )
    task = PipelineTask(
        task_id="task_sources_1",
        job_id=job.job_id,
        run_id="run_1",
        stage_id="sources",
        source_id="src_1",
        status=TaskStatus.COMPLETED,
    )
    state = PipelineState(
        run_id="run_1",
        job_id=job.job_id,
        status=PipelineRunStatus.RUNNING,
        tasks={task.task_id: task},
        completed_stage_ids=("sources",),
    )
    event = PipelineEvent(
        event_id="event_1",
        event_type=PipelineEventType.TASK_COMPLETED,
        run_id="run_1",
        job_id=job.job_id,
        task_id=task.task_id,
        stage_id=task.stage_id,
    )
    manifest = PipelineManifest(
        manifest_version="v1",
        run_id="run_1",
        job=job,
        stages=(),
        state=state,
        events=(event,),
    )

    assert manifest.state.tasks["task_sources_1"].status is TaskStatus.COMPLETED
    assert manifest.events[0].event_type is PipelineEventType.TASK_COMPLETED


def test_retry_evaluation_is_separate_from_stage_result() -> None:
    evaluation = RetryEvaluation(
        decision=RetryDecision.RETRY_LATER,
        next_attempt=2,
        delay_seconds=60,
        reason="Transient runtime error.",
    )

    assert evaluation.decision is RetryDecision.RETRY_LATER
    assert evaluation.next_attempt == 2
