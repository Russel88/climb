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

// ts/personal/workout-planner.ts
function mustElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}
var sourceSelect = mustElement("sessionSource");
var templateWrap = mustElement("templateWrap");
var templateIdSelect = mustElement("templateId");
var modeSelect = mustElement("sessionMode");
var dateInput = mustElement("sessionDate");
var bodyweightInput = mustElement("sessionBodyweight");
var exerciseSelectionWrap = mustElement("exerciseSelectionWrap");
var plannerExerciseList = mustElement("plannerExerciseList");
var previewButton = mustElement("previewSession");
var startButton = mustElement("startSession");
var previewPanel = mustElement("sessionPreview");
var exercises = [];
var templates = [];
function setDefaultDate() {
  const now = /* @__PURE__ */ new Date();
  const iso = now.toISOString().slice(0, 10);
  dateInput.value = iso;
}
function renderExerciseSelection() {
  plannerExerciseList.innerHTML = "";
  exercises.forEach((exercise, index) => {
    const row = document.createElement("div");
    row.className = "item-row selector-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = String(exercise.id);
    checkbox.className = "selector-check";
    const position = document.createElement("input");
    position.type = "number";
    position.min = "1";
    position.value = String(index + 1);
    position.className = "selector-position";
    position.dataset.role = "position";
    const text = document.createElement("span");
    text.className = "selector-label";
    text.textContent = `${exercise.name} (${exercise.kind})`;
    row.append(checkbox, text, position);
    plannerExerciseList.appendChild(row);
  });
}
function renderTemplates() {
  templateIdSelect.innerHTML = "";
  templates.forEach((template) => {
    const option = document.createElement("option");
    option.value = String(template.id);
    option.textContent = template.name;
    templateIdSelect.appendChild(option);
  });
}
function selectedExerciseIds() {
  return Array.from(plannerExerciseList.querySelectorAll(".item-row")).map((row) => {
    const checkbox = row.querySelector('input[type="checkbox"]');
    const position = row.querySelector('input[data-role="position"]');
    return {
      checked: Boolean(checkbox?.checked),
      exerciseId: Number(checkbox?.value ?? 0),
      position: Number(position?.value || 0)
    };
  }).filter((entry) => entry.checked).sort((a, b) => a.position - b.position).map((entry) => entry.exerciseId);
}
function buildPayload() {
  const source = sourceSelect.value;
  const payload = {
    source,
    mode: modeSelect.value,
    session_date: dateInput.value
  };
  if (bodyweightInput.value.trim()) {
    payload.bodyweight_kg = Number(bodyweightInput.value);
  }
  if (source === "template") {
    payload.template_id = Number(templateIdSelect.value);
  } else {
    payload.exercise_ids = selectedExerciseIds();
  }
  return payload;
}
function refreshSourceMode() {
  const isTemplate = sourceSelect.value === "template";
  templateWrap.classList.toggle("hidden", !isTemplate);
  exerciseSelectionWrap.classList.toggle("hidden", isTemplate);
}
function renderPreview(data) {
  previewPanel.innerHTML = "";
  previewPanel.appendChild(line(`Cycle ${data.cycle_number}, week ${data.cycle_week}`));
  previewPanel.appendChild(line(`Tasks: ${data.task_count}`));
  if (data.first_task) {
    previewPanel.appendChild(
      line(
        `First: ${data.first_task.exercise_name}${data.first_task.planned_weight_kg == null ? "" : `, ${data.first_task.planned_weight_kg} kg`}${data.first_task.planned_reps == null ? "" : `, ${data.first_task.planned_reps} reps`}`
      )
    );
  }
}
function line(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element;
}
async function loadData() {
  const [exerciseData, templateData, bodyweightData] = await Promise.all([
    apiGet("/personal/api/exercises"),
    apiGet("/personal/api/templates"),
    apiGet("/personal/api/bodyweight/latest")
  ]);
  exercises = exerciseData;
  templates = templateData;
  renderExerciseSelection();
  renderTemplates();
  if (bodyweightData.bodyweight_kg != null) {
    bodyweightInput.value = String(bodyweightData.bodyweight_kg);
  }
}
sourceSelect.addEventListener("change", refreshSourceMode);
previewButton.addEventListener("click", async () => {
  try {
    const preview = await apiPost("/personal/api/workout-sessions/preview", buildPayload());
    renderPreview(preview);
  } catch (error) {
    setToast(previewPanel, errorMessage(error), true);
  }
});
startButton.addEventListener("click", async () => {
  try {
    const session = await apiPost("/personal/api/workout-sessions", buildPayload());
    window.location.href = `/personal/workouts/${session.id}/run`;
  } catch (error) {
    setToast(previewPanel, errorMessage(error), true);
  }
});
setDefaultDate();
refreshSourceMode();
loadData().catch((error) => setToast(previewPanel, errorMessage(error), true));
