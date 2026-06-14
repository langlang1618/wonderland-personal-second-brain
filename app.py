"""Wonderland local web UI for creating Obsidian knowledge notes."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_knowledge_pipeline.modules.profiles import (
    DEFAULT_PROFILE_ID,
    KnowledgeProductProfile,
    ProfileRegistry,
    UnknownProfileError,
)


APP_ROOT = Path(__file__).resolve().parent
JOBS_DIR = APP_ROOT / "data" / "jobs"
INDEX_HTML = APP_ROOT / "templates" / "index.html"
HISTORY_LIMIT = 50
CANCEL_TIMEOUT_SECONDS = 5
PROFILE_REGISTRY = ProfileRegistry()


class JobCreateRequest(BaseModel):
    """Request payload for creating one Wonderland job."""

    source: str = Field(min_length=1)
    title: str = Field(min_length=1)
    profile_id: str | None = None


@dataclass(slots=True)
class JobRecord:
    """Job state mirrored by an on-disk history file and log file."""

    job_id: str
    source: str
    title: str | None
    status: str = "queued"
    log_path: Path = field(default_factory=Path)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    returncode: int | None = None
    obsidian_note_path: str | None = None
    error: str | None = None
    pid: int | None = None
    profile_id: str = DEFAULT_PROFILE_ID
    profile_display_name: str = "Finance"
    prompt_profile: str = "finance"
    output_folder: str = "AI Knowledge Pipeline/finance"
    process: asyncio.subprocess.Process | None = field(default=None, repr=False, compare=False)


app = FastAPI(title="Wonderland")
app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")
JOBS: dict[str, JobRecord] = {}


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Return the local Wonderland page."""

    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.post("/api/jobs")
async def create_job(payload: JobCreateRequest) -> dict[str, Any]:
    """Create a local processing job and start it in the background."""

    source = payload.source.strip()
    if not source:
        raise HTTPException(
            status_code=400,
            detail="Please enter a source link or local file path.",
        )
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Please enter a note title.")
    profile = _resolve_profile(payload.profile_id)
    job_id = uuid.uuid4().hex
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = JOBS_DIR / f"{job_id}.log"
    record = JobRecord(
        job_id=job_id,
        source=source,
        title=title,
        log_path=log_path,
        profile_id=profile.id,
        profile_display_name=profile.display_name,
        prompt_profile=profile.effective_prompt_profile,
        output_folder=str(profile.output_folder),
    )
    JOBS[job_id] = record
    _persist_job(record)
    _create_background_task(_run_job(record))
    return _job_payload(record)


@app.get("/api/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    """Return recently created Wonderland jobs from durable history."""

    return [_job_payload(record) for record in _read_history()]


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Return current job state."""

    return _job_payload(_get_job(job_id))


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    """Cancel a running Wonderland job."""

    record = _get_job(job_id)
    if record.status not in {"queued", "running"}:
        return _job_payload(record)
    await _cancel_job(record)
    return _job_payload(record)


@app.get("/api/jobs/{job_id}/log", response_class=PlainTextResponse)
async def get_job_log(job_id: str) -> PlainTextResponse:
    """Return the current job log."""

    record = _get_job(job_id)
    if not record.log_path.exists():
        return PlainTextResponse("")
    return PlainTextResponse(record.log_path.read_text(encoding="utf-8", errors="replace"))


async def _run_job(record: JobRecord) -> None:
    """Run the existing full-course CLI and stream output into the job log."""

    if record.status == "cancelled":
        _persist_job(record)
        return
    record.status = "running"
    record.updated_at = datetime.now(timezone.utc).isoformat()
    _persist_job(record)
    profile = _resolve_profile(record.profile_id)
    command = _build_command(record.source, record.title, profile)
    _write_log_header(record, command)
    env = os.environ.copy()
    env["PYTHONPATH"] = _merge_pythonpath(env.get("PYTHONPATH"))

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=APP_ROOT,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:
        record.status = "failed"
        record.error = str(exc)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        _append_log(record.log_path, f"Failed to start: {exc}\n")
        _persist_job(record)
        return

    record.process = process
    record.pid = process.pid
    record.updated_at = datetime.now(timezone.utc).isoformat()
    _persist_job(record)
    assert process.stdout is not None
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace")
        _append_log(record.log_path, text)
        note_path = _extract_obsidian_note_path(text)
        if note_path:
            record.obsidian_note_path = note_path

    returncode = await process.wait()
    record.returncode = returncode
    record.updated_at = datetime.now(timezone.utc).isoformat()
    record.process = None
    log_text = record.log_path.read_text(encoding="utf-8", errors="replace")
    record.obsidian_note_path = record.obsidian_note_path or _extract_obsidian_note_path(
        log_text
    )
    if record.status == "cancelled":
        _persist_job(record)
        return
    if returncode == 0:
        record.status = "success"
        _append_log(record.log_path, "\nCompleted\n")
    else:
        record.status = "failed"
        record.error = f"Command exited with code {returncode}"
        _append_log(record.log_path, f"\nFailed with exit code {returncode}\n")
    _persist_job(record)


async def _cancel_job(record: JobRecord) -> None:
    """Terminate a running job process and persist cancelled state."""

    _append_log(record.log_path, "\nCancelled by user\n")
    process = record.process
    if process is not None and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=CANCEL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        record.returncode = process.returncode
    elif record.pid is not None:
        _append_log(record.log_path, "Process handle unavailable; status marked cancelled.\n")
    record.status = "cancelled"
    record.error = "Cancelled by user"
    record.updated_at = datetime.now(timezone.utc).isoformat()
    record.process = None
    _persist_job(record)


def _build_command(
    source: str,
    title: str | None,
    profile: KnowledgeProductProfile | None = None,
) -> list[str]:
    """Build the v1.3.2 CLI command with Wonderland defaults."""

    selected_profile = profile or PROFILE_REGISTRY.get(DEFAULT_PROFILE_ID)
    command = [
        str(_python_executable()),
        "scripts/run_full_course_pipeline.py",
        "--source",
        source,
        "--source-type",
        "auto",
        "--profile",
        selected_profile.effective_prompt_profile,
        "--tags",
        ",".join(selected_profile.tags),
        "--model-size",
        "small",
        "--language",
        "zh",
        "--chunk-minutes",
        "30",
        "--cleanup",
        "raw,chunks",
        "--skip-existing",
    ]
    if title:
        command.extend(["--title", title])
    return command


def _python_executable() -> Path:
    venv_python = APP_ROOT / "venv" / "bin" / "python"
    return venv_python if venv_python.exists() else Path(sys.executable)


def _create_background_task(coro) -> asyncio.Task:
    return asyncio.create_task(coro)


def _job_payload(record: JobRecord) -> dict[str, Any]:
    return {
        "job_id": record.job_id,
        "source": record.source,
        "title": record.title,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "returncode": record.returncode,
        "obsidian_note_path": record.obsidian_note_path,
        "error": record.error,
        "log_path": str(record.log_path),
        "pid": record.pid,
        "profile_id": record.profile_id,
        "profile_display_name": record.profile_display_name,
        "prompt_profile": record.prompt_profile,
        "output_folder": record.output_folder,
    }


def _get_job(job_id: str) -> JobRecord:
    if job_id in JOBS:
        return JOBS[job_id]
    for record in _read_history():
        if record.job_id == job_id:
            JOBS[job_id] = record
            return record
    raise HTTPException(status_code=404, detail="Job not found.")


def _history_path() -> Path:
    return JOBS_DIR / "history.json"


def _read_history() -> list[JobRecord]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        raw_jobs = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw_jobs, list):
        return []
    records: list[JobRecord] = []
    for item in raw_jobs:
        if isinstance(item, dict):
            records.append(_record_from_history(item))
    return sorted(records, key=lambda record: record.created_at, reverse=True)


def _persist_job(record: JobRecord) -> None:
    jobs_by_id = {existing.job_id: existing for existing in _read_history()}
    jobs_by_id[record.job_id] = record
    records = sorted(jobs_by_id.values(), key=lambda item: item.created_at, reverse=True)[
        :HISTORY_LIMIT
    ]
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([_job_payload(item) for item in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _record_from_history(item: dict[str, Any]) -> JobRecord:
    return JobRecord(
        job_id=str(item.get("job_id", "")),
        source=str(item.get("source", "")),
        title=item.get("title"),
        status=str(item.get("status", "queued")),
        log_path=Path(str(item.get("log_path", ""))),
        created_at=str(item.get("created_at", datetime.now(timezone.utc).isoformat())),
        updated_at=str(item.get("updated_at", datetime.now(timezone.utc).isoformat())),
        returncode=item.get("returncode"),
        obsidian_note_path=item.get("obsidian_note_path"),
        error=item.get("error"),
        pid=item.get("pid"),
        profile_id=str(item.get("profile_id", DEFAULT_PROFILE_ID)),
        profile_display_name=str(item.get("profile_display_name", "Finance")),
        prompt_profile=str(item.get("prompt_profile", "finance")),
        output_folder=str(item.get("output_folder", "AI Knowledge Pipeline/finance")),
    )


def _resolve_profile(profile_id: str | None) -> KnowledgeProductProfile:
    try:
        return PROFILE_REGISTRY.get(profile_id)
    except UnknownProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _write_log_header(record: JobRecord, command: list[str]) -> None:
    _append_log(
        record.log_path,
        "\n".join(
            [
                "Starting Wonderland job",
                f"job_id: {record.job_id}",
                f"created_at: {record.created_at}",
                f"source: {record.source}",
                f"title: {record.title or ''}",
                f"profile: {record.profile_display_name} ({record.profile_id})",
                f"output_folder: {record.output_folder}",
                "Running full course pipeline",
                "Detecting source",
                "Extracting audio",
                "Chunking audio",
                "Transcribing",
                "Cleaning transcript",
                "Writing Obsidian note",
                f"command: {_redacted_command(command)}",
                "",
            ]
        ),
    )


def _append_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(text)


def _extract_obsidian_note_path(text: str) -> str | None:
    matches = re.findall(r"obsidian_note_path:\s*(.+)", text)
    for match in reversed(matches):
        value = match.strip()
        if value and value != "None":
            return value
    return None


def _merge_pythonpath(existing: str | None) -> str:
    return str(APP_ROOT) if not existing else os.pathsep.join((str(APP_ROOT), existing))


def _redacted_command(command: list[str]) -> str:
    return " ".join(command)
