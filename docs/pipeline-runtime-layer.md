# Pipeline Runtime Layer

This document designs the orchestration boundary for AI Knowledge Pipeline. It defines schemas and contracts only. It does not implement downloader logic, business stage logic, scheduling, queue workers, async execution, or persistence side effects.

## Goals

The runtime layer should make the future pipeline:

- composable
- traceable
- resumable
- observable
- extensible
- compatible with LangGraph, agent orchestration, async execution, queues, and distributed workers

## Architecture

```text
PipelineJob
  -> PipelineRuntime.submit()
  -> PipelineManifest
  -> PipelineTask graph
  -> PipelineStageExecutor.execute()
  -> StepResult
  -> PipelineState update
  -> PipelineEvent append
  -> PipelineManifest snapshot
```

The runtime boundary is stage-agnostic. It knows that stages exist, have dependencies, emit artifacts, return results, and may fail or retry. It does not know how to download media, run Whisper, call OpenAI, or write Obsidian files.

## File Organization

```text
ai_knowledge_pipeline/
└── core/
    └── runtime.py
```

`core/runtime.py`
: Shared runtime contracts for jobs, tasks, stages, state, events, retries, errors, logs, and manifests.

Runtime types live in `core` because every module will use them. Stage implementations can depend on the runtime contract, while the runtime does not depend on any specific module implementation.

## Pipeline Stage Model

`PipelineStageSpec` is a static definition of a stage:

- `stage_id`
- `kind`
- `name`
- `version`
- `depends_on`
- `execution_mode`
- `retry_policy`
- `input_contract`
- `output_contract`
- `tags`
- `metadata`

Canonical stage kinds:

- `sources`
- `download`
- `chunking`
- `transcription`
- `cleaning`
- `markdown`
- `obsidian`

Execution modes:

- `sync`
- `async`
- `queued`
- `agent`

The `agent` mode is reserved for future stages where an AI agent or LangGraph node may decide, repair, enrich, or route work.

## Task And Job Model

`PipelineJob` is the user-submitted unit of work. It describes source ids, requested stages, config profile, and metadata.

`PipelineTask` is an executable unit derived from a job. A task binds one stage to a run and optionally to one source id. This shape supports both single-source workflows and batch workflows.

Important task fields:

- `task_id`
- `job_id`
- `run_id`
- `stage_id`
- `source_id`
- `status`
- `attempt`
- `max_attempts`
- `depends_on`
- `assigned_worker`
- `input_artifacts`
- `output_artifacts`

This task model is intentionally compatible with local execution, async schedulers, queues, and distributed workers.

## Pipeline State Model

`PipelineState` is a serializable snapshot of a run:

- run id
- job id
- run status
- task map
- completed stage ids
- failed task ids
- artifact map
- accumulated errors
- metadata

State should be treated as append-friendly and resumable. A future implementation can persist it after every step or after every event.

## Execution Context

`ExecutionContext` is passed to a stage executor:

- run id
- job id
- task id
- stage spec
- config profile
- correlation id
- worker id
- optional state snapshot
- metadata

The context gives stages enough runtime information without coupling them to a concrete scheduler or storage implementation.

## Step Result Contract

`StepResult` is returned by every stage executor:

- task id
- stage id
- outcome
- output artifacts
- state patch
- errors
- events
- retry delay hint
- metadata

Outcomes:

- `success`
- `failure`
- `skipped`
- `retryable_failure`

The runtime should only rely on this contract, not on stage-specific return values.

## Retry Strategy Model

`RetryPolicy` defines:

- max attempts
- backoff strategy
- initial delay
- max delay
- retryable error codes

Backoff strategies:

- `none`
- `fixed`
- `exponential`

`RetryStrategy` evaluates a failed `StepResult` and returns `RetryEvaluation`:

- `do_not_retry`
- `retry_now`
- `retry_later`
- `escalate`

This keeps retry policy separate from stage logic. Download, transcription, and AI cleaning will likely need different retry profiles.

## Error Propagation Strategy

Runtime errors are structured as `PipelineError`:

- stable error code
- message
- severity
- stage id
- task id
- cause
- details

Errors should flow upward like this:

```text
stage executor
  -> StepResult.errors
  -> PipelineState.errors
  -> PipelineEvent payload
  -> PipelineManifest snapshot
  -> CLI / Agent / UI / queue monitor
```

Fatal errors can stop the run. Retryable errors can schedule a retry. Warning-level errors can be preserved without failing the task.

## Logging Contract

`PipelineLogger` accepts structured `LogRecord` values:

- level
- message
- run id
- job id
- task id
- stage id
- correlation id
- metadata

This contract allows later adapters for stdout, JSONL files, OpenTelemetry, cloud logging, or queue dashboards.

## Event Model

`PipelineEvent` is append-only and records runtime transitions.

Event types:

- job created
- run started
- task created
- task started
- task retry scheduled
- task completed
- task failed
- artifact recorded
- run paused
- run completed
- run failed

Events are the bridge to observability, replay, debugging, LangGraph state inspection, and future distributed worker coordination.

## Pipeline Manifest Lifecycle

`PipelineManifest` is the durable run envelope:

- manifest version
- run id
- job
- stage specs
- current state
- events
- artifacts
- metadata

Lifecycle:

```text
created
  -> submitted
  -> running
  -> snapshot after each task/event
  -> paused / failed / completed
  -> resumable from manifest
```

Planned locations:

```text
data/raw/pipeline-runs/{run_id}.json
data/raw/pipeline-events/{run_id}.jsonl
```

Config:

```yaml
runtime:
  manifest_dir: data/raw/pipeline-runs
  event_log_dir: data/raw/pipeline-events
  enable_event_log: true
  enable_resume: true
  max_concurrent_tasks: 1
```

## How Pipeline Runs

1. A caller creates a `PipelineJob`.
2. `PipelineRuntime.submit()` creates a `PipelineManifest`.
3. The runtime expands requested stages into `PipelineTask` records.
4. The scheduler selects ready tasks based on dependencies.
5. A `PipelineStageExecutor` receives an `ExecutionContext`.
6. The executor returns a `StepResult`.
7. The runtime updates `PipelineState`, emits events, records artifacts, and saves a manifest snapshot.
8. The run completes, fails, pauses, or remains ready for the next step.

## How State Flows

State is not hidden inside modules. It flows through explicit contracts:

```text
PipelineManifest.state
  -> ExecutionContext.state
  -> StepResult.state_patch
  -> PipelineState
  -> PipelineManifest.state
```

Artifacts also become state. Every media file, chunk, transcript, Markdown file, and Obsidian note should eventually become a `RuntimeArtifact` linked back to a source id.

## How Errors Propagate

Stage-specific failures are converted into `PipelineError` and returned through `StepResult.errors`.

The runtime then decides:

- retry the task
- mark the task failed
- skip dependent tasks
- pause for human or agent intervention
- fail the run

The original error remains traceable through events, state, logs, and manifest snapshots.

## How Retry Works

Retry is policy-driven:

```text
StepResult(outcome=retryable_failure)
  -> RetryStrategy.evaluate()
  -> RetryEvaluation
  -> task status retrying / failed / escalated
  -> PipelineEvent(task_retry_scheduled)
```

The stage reports what happened. The retry strategy decides what to do next. This keeps business modules simple and makes retry behavior configurable.

## AI Agent Handoff Points

Future AI agent or LangGraph nodes fit naturally at:

- source ambiguity resolution
- source metadata enrichment
- transcript cleanup
- terminology repair
- summary and knowledge point extraction
- failed-step diagnosis
- retry/escalation decision
- Obsidian classification and routing
- RAG indexing strategy
- memory write policy

The `StageExecutionMode.AGENT` enum exists so these nodes can be modeled without changing the runtime contract.

## Supporting Multi-Task Concurrency

Concurrency is supported by design through:

- task ids
- dependency lists
- task status
- assigned worker ids
- max concurrent task config
- idempotent artifact references
- append-only events
- resumable manifest snapshots

A local runtime can start with `max_concurrent_tasks: 1`. Later, a queue runtime can dispatch ready tasks to workers while preserving the same `PipelineTask`, `ExecutionContext`, `StepResult`, and `PipelineEvent` contracts.
