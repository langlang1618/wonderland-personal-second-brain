const form = document.querySelector("#job-form");
const sourceInput = document.querySelector("#source");
const titleInput = document.querySelector("#title");
const profileSelect = document.querySelector("#profile");
const startButton = document.querySelector("#start-button");
const stopButton = document.querySelector("#stop-button");
const statusText = document.querySelector("#status");
const notePath = document.querySelector("#note-path");
const logOutput = document.querySelector("#log-output");
const jobIdText = document.querySelector("#job-id");
const logPanel = document.querySelector("#log-panel");
const logToggle = document.querySelector("#log-toggle");
const resultCard = document.querySelector("#result-card");
const recentCard = document.querySelector("#recent-card");
const recentJobCount = document.querySelector("#recent-job-count");
const recentJobsList = document.querySelector("#recent-jobs-list");

let activeJobId = null;
let pollTimer = null;
let recentJobs = [];

logToggle.addEventListener("click", () => {
  const isCollapsed = logPanel.classList.toggle("is-collapsed");
  logToggle.textContent = isCollapsed ? "Show Logs" : "Hide Logs";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const source = sourceInput.value.trim();
  const title = titleInput.value.trim();
  const profileId = profileSelect.value || "finance";
  if (!source) {
    showValidationMessage("Please enter a source link or local file path.");
    sourceInput.focus();
    return;
  }
  if (!title) {
    showValidationMessage("Please enter a note title.");
    titleInput.focus();
    return;
  }

  setStatus("Creating", "creating");
  setRunningControls(true);
  logOutput.textContent = "Starting Wonderland...\n";
  notePath.textContent = "Waiting for completion";
  resultCard.classList.remove("is-active");

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, title, profile_id: profileId }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Unable to start");
    }
    activeJobId = payload.job_id;
    jobIdText.textContent = activeJobId;
    updateRecentJob(payload);
    await refreshJob();
    pollTimer = window.setInterval(refreshJob, 2000);
  } catch (error) {
    stopPolling();
    setStatus("Failed", "failed");
    logOutput.textContent += `${error.message}\n`;
    notePath.textContent = "Something went wrong. Show logs for details.";
    setRunningControls(false);
  }
});

stopButton.addEventListener("click", async () => {
  if (!activeJobId) return;
  stopButton.disabled = true;
  stopButton.textContent = "Stopping...";
  try {
    const response = await fetch(`/api/jobs/${activeJobId}/cancel`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Unable to stop");
    }
    await refreshJob();
  } catch (error) {
    logOutput.textContent += `\n${error.message}\n`;
    stopButton.disabled = false;
    stopButton.textContent = "Stop";
  }
});

window.addEventListener("load", restoreLatestJob);

async function refreshJob() {
  if (!activeJobId) return;

  const [statusResponse, logResponse] = await Promise.all([
    fetch(`/api/jobs/${activeJobId}`),
    fetch(`/api/jobs/${activeJobId}/log`),
  ]);
  const payload = await statusResponse.json();
  const logText = await logResponse.text();

  logOutput.textContent = logText || "Waiting for logs...";
  logOutput.scrollTop = logOutput.scrollHeight;
  setStatus(displayStatus(payload.status), stateName(payload.status));
  if (payload.obsidian_note_path) {
    notePath.textContent = payload.obsidian_note_path;
  }
  updateRecentJob(payload);

  if (payload.status === "queued" || payload.status === "running") {
    setRunningControls(true);
  }

  if (payload.status === "success") {
    setStatus("Completed", "completed");
    resultCard.classList.add("is-active");
    stopPolling();
    setRunningControls(false);
  }

  if (payload.status === "failed") {
    setStatus("Failed", "failed");
    resultCard.classList.remove("is-active");
    if (payload.error) {
      logOutput.textContent += `\n${payload.error}\n`;
    }
    notePath.textContent = payload.obsidian_note_path || "Something went wrong. Show logs for details.";
    stopPolling();
    setRunningControls(false);
  }

  if (payload.status === "cancelled") {
    setStatus("Cancelled", "failed");
    resultCard.classList.remove("is-active");
    notePath.textContent = payload.obsidian_note_path || "Stopped before completion.";
    stopPolling();
    setRunningControls(false);
  }
}

async function restoreLatestJob() {
  try {
    const response = await fetch("/api/jobs");
    if (!response.ok) return;
    const jobs = await response.json();
    if (!Array.isArray(jobs) || jobs.length === 0) return;
    const latestJob = jobs[0];
    renderRecentJobs(jobs);
    if (latestJob.status === "running" || latestJob.status === "queued") {
      activeJobId = latestJob.job_id;
      jobIdText.textContent = activeJobId;
      sourceInput.value = latestJob.source || sourceInput.value;
      titleInput.value = latestJob.title || titleInput.value;
      profileSelect.value = latestJob.profile_id || profileSelect.value;
      setStatus(displayStatus(latestJob.status), stateName(latestJob.status));
      setRunningControls(true);
      await refreshJob();
      pollTimer = window.setInterval(refreshJob, 2000);
    } else if (latestJob.obsidian_note_path) {
      notePath.textContent = latestJob.obsidian_note_path;
      resultCard.classList.add("is-active");
      setStatus(displayStatus(latestJob.status), stateName(latestJob.status));
    }
  } catch (error) {
    logOutput.textContent = `Wonderland is ready.\n${error.message}\n`;
  }
}

function showValidationMessage(message) {
  stopPolling();
  setStatus(message, "failed");
  logOutput.textContent = message;
  notePath.textContent = "Waiting for your first note";
  resultCard.classList.remove("is-active");
  setRunningControls(false);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function displayStatus(status) {
  if (status === "queued") return "Queued";
  if (status === "running") return "Creating";
  if (status === "success") return "Completed";
  if (status === "failed") return "Failed";
  if (status === "cancelled") return "Cancelled";
  return "Idle";
}

function stateName(status) {
  if (status === "running" || status === "queued") return "creating";
  if (status === "success") return "completed";
  if (status === "failed" || status === "cancelled") return "failed";
  return "idle";
}

function setStatus(text, state) {
  statusText.textContent = text;
  statusText.dataset.state = state;
}

function setRunningControls(isRunning) {
  startButton.textContent = isRunning ? "Creating..." : "Start";
  startButton.disabled = isRunning;
  stopButton.hidden = !isRunning;
  stopButton.disabled = false;
  stopButton.textContent = "Stop";
}

function renderRecentJobs(jobs) {
  if (!Array.isArray(jobs) || jobs.length === 0) return;
  recentJobs = jobs;
  recentCard.hidden = false;
  recentJobCount.textContent = `${jobs.length}`;
  recentJobsList.replaceChildren(...jobs.slice(0, 8).map(renderRecentJobItem));
}

function updateRecentJob(job) {
  if (!job || !job.job_id) return;
  const existingIndex = recentJobs.findIndex((item) => item.job_id === job.job_id);
  if (existingIndex >= 0) {
    recentJobs[existingIndex] = job;
  } else {
    recentJobs = [job, ...recentJobs];
  }
  renderRecentJobs(recentJobs);
}

function renderRecentJobItem(job) {
  const item = document.createElement("article");
  item.className = "recent-job-item";
  if (job.job_id === activeJobId) {
    item.classList.add("is-active");
  }

  const main = document.createElement("div");
  main.className = "recent-job-main";

  const title = document.createElement("strong");
  title.textContent = job.title || "Untitled";

  const meta = document.createElement("span");
  meta.textContent = `${job.profile_display_name || "Finance"} / ${displayStatus(job.status)} · ${formatDate(job.created_at)}`;

  main.append(title, meta);
  item.append(main);

  if (job.obsidian_note_path) {
    const path = document.createElement("p");
    path.className = "recent-note-path";
    path.textContent = job.obsidian_note_path;
    item.append(path);
  }

  const logButton = document.createElement("button");
  logButton.className = "recent-log-button";
  logButton.type = "button";
  logButton.textContent = "Log";
  logButton.addEventListener("click", () => {
    activeJobId = job.job_id;
    jobIdText.textContent = activeJobId;
    sourceInput.value = job.source || sourceInput.value;
    titleInput.value = job.title || titleInput.value;
    profileSelect.value = job.profile_id || profileSelect.value;
    logPanel.classList.remove("is-collapsed");
    logToggle.textContent = "Hide Logs";
    refreshJob();
  });
  item.append(logButton);
  return item;
}

function formatDate(value) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
