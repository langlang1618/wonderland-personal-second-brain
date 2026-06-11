from pathlib import Path

from fastapi.testclient import TestClient

import app as wonderland


def test_wonderland_home_renders_product_page() -> None:
    client = TestClient(wonderland.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Wonderland" in response.text
    assert "Local AI Second Brain" in response.text
    assert "Create a knowledge note" in response.text
    assert "Turn courses, videos, audio and links into Obsidian knowledge notes." in response.text
    assert 'id="title"' in response.text
    assert "Give your note a clear title" in response.text
    assert "Show Logs" in response.text
    assert "Start Pipeline" not in response.text
    assert "Pipeline Status" not in response.text


def test_wonderland_create_job_uses_existing_full_runner_command(monkeypatch, tmp_path) -> None:
    wonderland.JOBS.clear()
    monkeypatch.setattr(wonderland, "JOBS_DIR", tmp_path / "jobs")

    def fake_create_background_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(wonderland, "_create_background_task", fake_create_background_task)
    client = TestClient(wonderland.app)

    response = client.post(
        "/api/jobs",
        json={"source": "https://example.com/course.m3u8", "title": "课程A"},
    )

    assert response.status_code == 200
    payload = response.json()
    job = wonderland.JOBS[payload["job_id"]]
    assert job.status == "queued"
    assert job.log_path == tmp_path / "jobs" / f"{job.job_id}.log"
    command = wonderland._build_command(job.source, job.title)
    assert command[1:] == [
        "scripts/run_full_course_pipeline.py",
        "--source",
        "https://example.com/course.m3u8",
        "--source-type",
        "auto",
        "--profile",
        "finance",
        "--tags",
        "finance,course,whisper-small,wonderland",
        "--model-size",
        "small",
        "--language",
        "zh",
        "--chunk-minutes",
        "30",
        "--cleanup",
        "raw,chunks",
        "--skip-existing",
        "--title",
        "课程A",
    ]


def test_wonderland_create_job_rejects_empty_source() -> None:
    client = TestClient(wonderland.app)

    response = client.post(
        "/api/jobs",
        json={"source": "   ", "title": "课程A"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Please enter a source link or local file path."


def test_wonderland_create_job_rejects_empty_title() -> None:
    client = TestClient(wonderland.app)

    response = client.post(
        "/api/jobs",
        json={"source": "https://example.com/course.m3u8", "title": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Please enter a note title."


def test_wonderland_job_status_and_log_endpoints(tmp_path) -> None:
    wonderland.JOBS.clear()
    log_path = tmp_path / "job.log"
    log_path.write_text("Completed\nobsidian_note_path: /vault/course.md\n", encoding="utf-8")
    record = wonderland.JobRecord(
        job_id="job-1",
        source="/tmp/course.mp4",
        title="课程A",
        status="success",
        log_path=log_path,
        obsidian_note_path="/vault/course.md",
    )
    wonderland.JOBS["job-1"] = record
    client = TestClient(wonderland.app)

    status_response = client.get("/api/jobs/job-1")
    log_response = client.get("/api/jobs/job-1/log")

    assert status_response.status_code == 200
    assert status_response.json()["obsidian_note_path"] == "/vault/course.md"
    assert log_response.status_code == 200
    assert "Completed" in log_response.text


def test_wonderland_extracts_obsidian_note_path_from_output() -> None:
    text = "\n".join(
        [
            "Full course pipeline completed:",
            "obsidian_note_path: /Users/langlang/Vault/Course.md",
            "cleanup: raw,chunks",
        ]
    )

    assert wonderland._extract_obsidian_note_path(text) == "/Users/langlang/Vault/Course.md"
