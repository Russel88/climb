// ts/personal/api-client.ts
async function apiGet(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  return handleResponse(response);
}
async function apiPost(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload ?? {})
  });
  return handleResponse(response);
}
function errorMessage(error) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
async function handleResponse(response) {
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { error: text };
    }
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    if (payload && typeof payload === "object" && "error" in payload) {
      const errorValue = payload.error;
      if (typeof errorValue === "string" && errorValue) {
        message = errorValue;
      }
    }
    throw new Error(message);
  }
  return payload;
}
function setToast(target, message, isError = false) {
  if (!target) {
    return;
  }
  target.textContent = message;
  target.classList.add("toast");
  target.classList.toggle("error", isError);
}

// ts/personal/workout-run.ts
function mustElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}
var sessionIdNode = mustElement("sessionId");
var taskCard = mustElement("taskCard");
var taskForm = mustElement("taskForm");
var repsWrap = mustElement("repsWrap");
var noteWrap = mustElement("noteWrap");
var actualRepsInput = mustElement("actualReps");
var taskNoteInput = mustElement("taskNote");
var finishSessionButton = mustElement("finishSession");
var sessionId = Number(sessionIdNode.textContent);
var session = null;
function renderSession() {
  taskCard.innerHTML = "";
  if (!session) {
    taskCard.appendChild(line("Session not loaded."));
    return;
  }
  taskCard.appendChild(line(`Task ${Math.min(session.next_task_index + 1, session.task_count)} of ${session.task_count}`));
  if (!session.current_task) {
    taskCard.appendChild(line("Workout complete."));
    taskForm.classList.add("hidden");
    return;
  }
  taskForm.classList.remove("hidden");
  const task = session.current_task;
  const details = [task.exercise_name];
  if (task.planned_weight_kg != null) {
    details.push(`${task.planned_weight_kg} kg`);
  }
  if (task.planned_reps != null) {
    details.push(`${task.planned_reps} reps`);
  }
  taskCard.appendChild(line(details.join(" | ")));
  const progressive = task.kind === "progressive";
  repsWrap.classList.toggle("hidden", !progressive);
  noteWrap.classList.toggle("hidden", progressive);
  actualRepsInput.value = "";
  taskNoteInput.value = "";
}
function line(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element;
}
async function loadSession() {
  session = await apiGet(`/personal/api/workout-sessions/${sessionId}`);
  renderSession();
}
taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!session?.current_task) {
    return;
  }
  const payload = {};
  if (session.current_task.kind === "progressive") {
    payload.actual_reps = Number(actualRepsInput.value);
  } else if (taskNoteInput.value.trim()) {
    payload.note = taskNoteInput.value.trim();
  }
  try {
    session = await apiPost(
      `/personal/api/workout-sessions/${session.id}/tasks/${session.next_task_index}/complete`,
      payload
    );
    renderSession();
  } catch (error) {
    setToast(taskCard, errorMessage(error), true);
  }
});
finishSessionButton.addEventListener("click", async () => {
  try {
    session = await apiPost(`/personal/api/workout-sessions/${sessionId}/finish`, {});
    renderSession();
  } catch (error) {
    setToast(taskCard, errorMessage(error), true);
  }
});
loadSession().catch((error) => setToast(taskCard, errorMessage(error), true));
