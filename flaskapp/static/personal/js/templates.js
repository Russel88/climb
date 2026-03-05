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
  const payload = text ? JSON.parse(text) : {};
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

// ts/personal/templates.ts
function mustElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}
var templateForm = mustElement("templateForm");
var templateRecordId = mustElement("templateRecordId");
var templateName = mustElement("templateName");
var templateExerciseList = mustElement("templateExerciseList");
var templateList = mustElement("templateList");
var templateFormReset = mustElement("templateFormReset");
var exercises = [];
var templates = [];
function renderExerciseSelector(selectedExerciseIds2 = []) {
  templateExerciseList.innerHTML = "";
  exercises.forEach((exercise, index) => {
    const row = document.createElement("div");
    row.className = "item-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = String(exercise.id);
    checkbox.checked = selectedExerciseIds2.includes(exercise.id);
    const position = document.createElement("input");
    position.type = "number";
    position.min = "1";
    position.value = String(
      selectedExerciseIds2.includes(exercise.id) ? selectedExerciseIds2.indexOf(exercise.id) + 1 : index + 1
    );
    position.style.maxWidth = "4.5rem";
    position.dataset.role = "position";
    const text = document.createElement("span");
    text.textContent = `${exercise.name} (${exercise.kind})`;
    row.append(checkbox, text, position);
    templateExerciseList.appendChild(row);
  });
}
function selectedExerciseIds() {
  const selection = Array.from(templateExerciseList.querySelectorAll(".item-row")).map((row) => {
    const checkbox = row.querySelector('input[type="checkbox"]');
    const position = row.querySelector('input[data-role="position"]');
    return {
      checked: Boolean(checkbox?.checked),
      exerciseId: Number(checkbox?.value ?? 0),
      position: Number(position?.value || 0)
    };
  });
  return selection.filter((entry) => entry.checked).sort((a, b) => a.position - b.position).map((entry) => entry.exerciseId);
}
function resetForm() {
  templateRecordId.value = "";
  templateName.value = "";
  renderExerciseSelector();
}
function editTemplate(template) {
  templateRecordId.value = String(template.id);
  templateName.value = template.name;
  renderExerciseSelector(template.items.map((item) => item.exercise_id));
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function renderTemplates() {
  templateList.innerHTML = "";
  templates.forEach((template) => {
    const row = document.createElement("div");
    row.className = "item-row";
    const details = document.createElement("div");
    const names = template.items.map((item) => item.exercise_name).join(" -> ");
    details.innerHTML = `<strong>${template.name}</strong><br><small>${names}</small>`;
    const actions = document.createElement("div");
    actions.className = "item-actions";
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "secondary";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => editTemplate(template));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "danger";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", async () => {
      if (!window.confirm(`Delete template ${template.name}?`)) {
        return;
      }
      try {
        await apiDelete(`/personal/api/templates/${template.id}`);
        await loadData();
      } catch (error) {
        setToast(templateList, errorMessage(error), true);
      }
    });
    actions.append(editButton, deleteButton);
    row.append(details, actions);
    templateList.appendChild(row);
  });
}
async function loadData() {
  const [exerciseResult, templateResult] = await Promise.all([
    apiGet("/personal/api/exercises"),
    apiGet("/personal/api/templates")
  ]);
  exercises = exerciseResult;
  templates = templateResult;
  renderExerciseSelector(selectedExerciseIds());
  renderTemplates();
}
templateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    name: templateName.value.trim(),
    exercise_ids: selectedExerciseIds()
  };
  try {
    if (templateRecordId.value) {
      await apiPut(`/personal/api/templates/${templateRecordId.value}`, payload);
    } else {
      await apiPost("/personal/api/templates", payload);
    }
    resetForm();
    await loadData();
  } catch (error) {
    setToast(templateList, errorMessage(error), true);
  }
});
templateFormReset.addEventListener("click", resetForm);
loadData().catch((error) => setToast(templateList, errorMessage(error), true));
