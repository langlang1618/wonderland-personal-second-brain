"""Wonderland local web UI for creating Obsidian knowledge notes."""

from __future__ import annotations

import asyncio
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


APP_ROOT = Path(__file__).resolve().parent
JOBS_DIR = APP_ROOT / "data" / "jobs"
INDEX_HTML = APP_ROOT / "templates" / "index.html"
DEFAULT_TAGS = "finance,course,whisper-small,wonderland"


class JobCreateRequest(BaseModel):
    """Request payload for creating one Wonderland job."""

    source: str = Field(min_length=1)
    title: str = Field(min_length=1)


@dataclass(slots=True)
class JobRecord:
    """In-memory job state mirrored by an on-disk log file."""

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
    job_id = uuid.uuid4().hex
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = JOBS_DIR / f"{job_id}.log"
    record = JobRecord(
        job_id=job_id,
        source=source,
        title=title,
        log_path=log_path,
    )
    JOBS[job_id] = record
    _create_background_task(_run_job(record))
    return _job_payload(record)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Return current job state."""

    return _job_payload(_get_job(job_id))


@app.get("/api/jobs/{job_id}/log", response_class=PlainTextResponse)
async def get_job_log(job_id: str) -> PlainTextResponse:
    """Return the current job log."""

    record = _get_job(job_id)
    if not record.log_path.exists():
        return PlainTextResponse("")
    return PlainTextResponse(record.log_path.read_text(encoding="utf-8", errors="replace"))


async def _run_job(record: JobRecord) -> None:
    """Run the existing full-course CLI and stream output into the job log."""

    record.status = "running"
    record.updated_at = datetime.now(timezone.utc).isoformat()
    command = _build_command(record.source, record.title)
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
        return

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
    log_text = record.log_path.read_text(encoding="utf-8", errors="replace")
    record.obsidian_note_path = record.obsidian_note_path or _extract_obsidian_note_path(
        log_text
    )
    if returncode == 0:
        record.status = "success"
        _append_log(record.log_path, "\nCompleted\n")
    else:
        record.status = "failed"
        record.error = f"Command exited with code {returncode}"
        _append_log(record.log_path, f"\nFailed with exit code {returncode}\n")


def _build_command(source: str, title: str | None) -> list[str]:
    """Build the v1.3.2 CLI command with Wonderland defaults."""

    command = [
        str(_python_executable()),
        "scripts/run_full_course_pipeline.py",
        "--source",
        source,
        "--source-type",
        "auto",
        "--profile",
        "finance",
        "--tags",
        DEFAULT_TAGS,
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
    }


def _get_job(job_id: str) -> JobRecord:
    try:
        return JOBS[job_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


def _write_log_header(record: JobRecord, command: list[str]) -> None:
    _append_log(
        record.log_path,
        "\n".join(
            [
                "Wonderland job started",
                f"job_id: {record.job_id}",
                f"created_at: {record.created_at}",
                f"source: {record.source}",
                f"title: {record.title or ''}",
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
