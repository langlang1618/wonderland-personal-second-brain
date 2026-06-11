const form = document.querySelector("#job-form");
const sourceInput = document.querySelector("#source");
const titleInput = document.querySelector("#title");
const startButton = document.querySelector("#start-button");
const statusText = document.querySelector("#status");
const notePath = document.querySelector("#note-path");
const logOutput = document.querySelector("#log-output");
const jobIdText = document.querySelector("#job-id");

let activeJobId = null;
let pollTimer = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const source = sourceInput.value.trim();
  const title = titleInput.value.trim();
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

  setRunningState("Creating your knowledge note...");
  logOutput.textContent = "Starting Wonderland...\n";
  notePath.textContent = "Waiting for completion";

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, title }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Unable to start");
    }
    activeJobId = payload.job_id;
    jobIdText.textContent = activeJobId;
    await refreshJob();
    pollTimer = window.setInterval(refreshJob, 2000);
  } catch (error) {
    stopPolling();
    statusText.textContent = "Failed";
    logOutput.textContent += `${error.message}\n`;
    startButton.disabled = false;
  }
});

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
  statusText.textContent = displayStatus(payload.status);
  if (payload.obsidian_note_path) {
    notePath.textContent = payload.obsidian_note_path;
  }

  if (payload.status === "success") {
    statusText.textContent = "Completed";
    stopPolling();
    startButton.disabled = false;
  }

  if (payload.status === "failed") {
    statusText.textContent = "Failed";
    if (payload.error) {
      logOutput.textContent += `\n${payload.error}\n`;
    }
    stopPolling();
    startButton.disabled = false;
  }
}

function setRunningState(message) {
  statusText.textContent = message;
  startButton.disabled = true;
}

function showValidationMessage(message) {
  stopPolling();
  statusText.textContent = message;
  logOutput.textContent = message;
  notePath.textContent = "Waiting for your first note";
  startButton.disabled = false;
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function displayStatus(status) {
  if (status === "queued") return "Queued";
  if (status === "running") return "Creating your knowledge note...";
  if (status === "success") return "Completed";
  if (status === "failed") return "Failed";
  return "Ready";
}
