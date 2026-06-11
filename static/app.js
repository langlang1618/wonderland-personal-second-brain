const form = document.querySelector("#job-form");
const sourceInput = document.querySelector("#source");
const titleInput = document.querySelector("#title");
const startButton = document.querySelector("#start-button");
const statusText = document.querySelector("#status");
const notePath = document.querySelector("#note-path");
const logOutput = document.querySelector("#log-output");
const jobIdText = document.querySelector("#job-id");
const logPanel = document.querySelector("#log-panel");
const logToggle = document.querySelector("#log-toggle");
const resultCard = document.querySelector("#result-card");

let activeJobId = null;
let pollTimer = null;

logToggle.addEventListener("click", () => {
  const isCollapsed = logPanel.classList.toggle("is-collapsed");
  logToggle.textContent = isCollapsed ? "Show Logs" : "Hide Logs";
});

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

  setStatus("Creating", "creating");
  startButton.textContent = "Creating...";
  startButton.disabled = true;
  logOutput.textContent = "Starting Wonderland...\n";
  notePath.textContent = "Waiting for completion";
  resultCard.classList.remove("is-active");

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
    setStatus("Failed", "failed");
    logOutput.textContent += `${error.message}\n`;
    notePath.textContent = "Something went wrong. Show logs for details.";
    startButton.textContent = "Start";
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
  setStatus(displayStatus(payload.status), stateName(payload.status));
  if (payload.obsidian_note_path) {
    notePath.textContent = payload.obsidian_note_path;
  }

  if (payload.status === "success") {
    setStatus("Completed", "completed");
    resultCard.classList.add("is-active");
    stopPolling();
    startButton.textContent = "Start";
    startButton.disabled = false;
  }

  if (payload.status === "failed") {
    setStatus("Failed", "failed");
    resultCard.classList.remove("is-active");
    if (payload.error) {
      logOutput.textContent += `\n${payload.error}\n`;
    }
    notePath.textContent = payload.obsidian_note_path || "Something went wrong. Show logs for details.";
    stopPolling();
    startButton.textContent = "Start";
    startButton.disabled = false;
  }
}

function showValidationMessage(message) {
  stopPolling();
  setStatus(message, "failed");
  logOutput.textContent = message;
  notePath.textContent = "Waiting for your first note";
  resultCard.classList.remove("is-active");
  startButton.textContent = "Start";
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
  if (status === "running") return "Creating";
  if (status === "success") return "Completed";
  if (status === "failed") return "Failed";
  return "Idle";
}

function stateName(status) {
  if (status === "running" || status === "queued") return "creating";
  if (status === "success") return "completed";
  if (status === "failed") return "failed";
  return "idle";
}

function setStatus(text, state) {
  statusText.textContent = text;
  statusText.dataset.state = state;
}
