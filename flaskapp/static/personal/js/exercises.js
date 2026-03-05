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
async function apiPut(url, payload) {
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload ?? {})
  });
  return handleResponse(response);
}
async function apiDelete(url) {
  const response = await fetch(url, {
    method: "DELETE",
    headers: { Accept: "application/json" }
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

// ts/personal/exercises.ts
function mustElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}
function mustInput(selector) {
  const input = weekPlanGrid.querySelector(selector);
  if (!input) {
    throw new Error(`Missing input ${selector}`);
  }
  return input;
}
var form = mustElement("exerciseForm");
var exerciseList = mustElement("exerciseList");
var exerciseIdInput = mustElement("exerciseId");
var nameInput = mustElement("name");
var kindSelect = mustElement("kind");
var loadKindWrap = mustElement("loadKindWrap");
var loadKindSelect = mustElement("loadKind");
var targetWeightInput = mustElement("targetWeight");
var incrementStepInput = mustElement("incrementStep");
var roundingStepInput = mustElement("roundingStep");
var weekPlanGrid = mustElement("weekPlanGrid");
var resetButton = mustElement("resetExerciseForm");
var cachedExercises = [];
var DEFAULT_WEEK_PERCENTS = {
  1: [40, 50, 60, 65, 75, 85],
  2: [40, 50, 60, 70, 80, 90],
  3: [40, 50, 60, 75, 85, 95],
  4: [40, 40, 50, 50, 60, 60]
};
function renderWeekPlanInputs() {
  weekPlanGrid.innerHTML = "";
  for (let week = 1; week <= 4; week += 1) {
    const wrapper = document.createElement("div");
    wrapper.className = "item-row";
    const defaults = DEFAULT_WEEK_PERCENTS[week];
    wrapper.innerHTML = `
      <div>
        <strong>Week ${week}</strong>
        <label>Sets<input type="number" min="1" step="1" data-week="${week}" data-field="sets" value="6"></label>
        <label>Target reps<input type="number" min="1" step="1" data-week="${week}" data-field="target_reps" value="5"></label>
        <label>Set % list<input type="text" data-week="${week}" data-field="target_percents" value="${defaults.join(", ")}"></label>
      </div>
    `;
    weekPlanGrid.appendChild(wrapper);
  }
}
function toggleProgressiveFields() {
  const progressive = kindSelect.value === "progressive";
  document.querySelectorAll(".progressive-only").forEach((node) => {
    node.classList.toggle("hidden", !progressive);
  });
  loadKindWrap.classList.toggle("hidden", !progressive);
}
function clearForm() {
  exerciseIdInput.value = "";
  nameInput.value = "";
  kindSelect.value = "progressive";
  loadKindSelect.value = "external";
  targetWeightInput.value = "";
  incrementStepInput.value = "";
  roundingStepInput.value = "";
  renderWeekPlanInputs();
  toggleProgressiveFields();
}
function weekPlanFromInputs() {
  const result = [];
  for (let week = 1; week <= 4; week += 1) {
    const sets = Number(mustInput(`[data-week="${week}"][data-field="sets"]`).value);
    const targetReps = Number(mustInput(`[data-week="${week}"][data-field="target_reps"]`).value);
    const percentsRaw = mustInput(`[data-week="${week}"][data-field="target_percents"]`).value;
    const targetPercents = percentsRaw.split(/[,\s]+/).map((value) => value.trim()).filter((value) => value.length > 0).map((value) => Number(value));
    result.push({
      week_no: week,
      sets,
      target_reps: targetReps,
      target_percents: targetPercents
    });
  }
  return result;
}
function payloadFromForm() {
  const kind = kindSelect.value;
  const payload = {
    name: nameInput.value.trim(),
    kind,
    is_active: true
  };
  if (kind === "progressive") {
    payload.load_kind = loadKindSelect.value;
    payload.target_added_weight_kg = Number(targetWeightInput.value);
    payload.increment_step_kg = Number(incrementStepInput.value);
    payload.rounding_step_kg = Number(roundingStepInput.value);
    payload.week_plan = weekPlanFromInputs();
  } else {
    payload.week_plan = [];
  }
  return payload;
}
function fillForm(exercise) {
  exerciseIdInput.value = String(exercise.id);
  nameInput.value = exercise.name;
  kindSelect.value = exercise.kind;
  toggleProgressiveFields();
  if (exercise.kind === "progressive") {
    loadKindSelect.value = exercise.load_kind || "external";
    targetWeightInput.value = String(exercise.target_added_weight_kg ?? "");
    incrementStepInput.value = String(exercise.increment_step_kg ?? "");
    roundingStepInput.value = String(exercise.rounding_step_kg ?? "");
    weekPlanGrid.querySelectorAll("input").forEach((input) => {
      input.value = "";
    });
    exercise.week_plan.forEach((week) => {
      mustInput(`[data-week="${week.week_no}"][data-field="sets"]`).value = String(week.sets);
      mustInput(`[data-week="${week.week_no}"][data-field="target_reps"]`).value = String(week.target_reps);
      const percents = week.target_percents?.length ? week.target_percents : [week.target_percent ?? 0];
      mustInput(`[data-week="${week.week_no}"][data-field="target_percents"]`).value = percents.join(", ");
    });
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function renderExerciseList() {
  exerciseList.innerHTML = "";
  cachedExercises.forEach((exercise) => {
    const row = document.createElement("div");
    row.className = "item-row";
    const details = document.createElement("div");
    details.innerHTML = `<strong>${exercise.name}</strong><br><small>${exercise.kind}</small>`;
    const actions = document.createElement("div");
    actions.className = "item-actions";
    const edit = document.createElement("button");
    edit.className = "secondary";
    edit.type = "button";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => fillForm(exercise));
    const remove = document.createElement("button");
    remove.className = "danger";
    remove.type = "button";
    remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Delete ${exercise.name}?`)) {
        return;
      }
      try {
        await apiDelete(`/personal/api/exercises/${exercise.id}`);
        await loadExercises();
      } catch (error) {
        setToast(exerciseList, errorMessage(error), true);
      }
    });
    actions.append(edit, remove);
    row.append(details, actions);
    exerciseList.appendChild(row);
  });
}
async function loadExercises() {
  cachedExercises = await apiGet("/personal/api/exercises");
  renderExerciseList();
}
kindSelect.addEventListener("change", toggleProgressiveFields);
resetButton.addEventListener("click", clearForm);
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = payloadFromForm();
    const id = exerciseIdInput.value;
    if (id) {
      await apiPut(`/personal/api/exercises/${id}`, payload);
    } else {
      await apiPost("/personal/api/exercises", payload);
    }
    clearForm();
    await loadExercises();
  } catch (error) {
    setToast(exerciseList, errorMessage(error), true);
  }
});
renderWeekPlanInputs();
toggleProgressiveFields();
loadExercises().catch((error) => setToast(exerciseList, errorMessage(error), true));
