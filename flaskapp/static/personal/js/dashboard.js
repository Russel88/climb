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

// ts/personal/dashboard.ts
function mustElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}
var cycleStatus = mustElement("cycleStatus");
var suggestions = mustElement("suggestions");
async function loadDashboard() {
  try {
    const state = await apiGet("/personal/api/cycle/state");
    cycleStatus.innerHTML = "";
    cycleStatus.appendChild(line(`Cycle number: ${state.cycle_number}`));
    cycleStatus.appendChild(line(`Cycle week: ${state.cycle_week}`));
    cycleStatus.appendChild(line(`Week 1 anchor Monday: ${state.anchor_monday}`));
    if (!state.should_prompt_suggestions) {
      suggestions.innerHTML = "";
      suggestions.appendChild(line("No pending cycle increase suggestions."));
      return;
    }
    const suggestionPayload = await apiGet("/personal/api/cycle/suggestions");
    renderSuggestions(suggestionPayload.suggestions || []);
  } catch (error) {
    setToast(cycleStatus, errorMessage(error), true);
  }
}
function renderSuggestions(list) {
  suggestions.innerHTML = "";
  if (!list.length) {
    suggestions.appendChild(line("No exercises qualify for increase this cycle."));
    const markButton = document.createElement("button");
    markButton.textContent = "Mark reviewed";
    markButton.addEventListener("click", async () => {
      try {
        await apiPost("/personal/api/cycle/suggestions/apply", { accepted_exercise_ids: [] });
        await loadDashboard();
      } catch (error) {
        setToast(suggestions, errorMessage(error), true);
      }
    });
    suggestions.appendChild(markButton);
    return;
  }
  const form = document.createElement("form");
  form.className = "stack";
  list.forEach((suggestion) => {
    const wrapper = document.createElement("label");
    wrapper.className = "item-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = String(suggestion.exercise_id);
    checkbox.checked = true;
    const details = document.createElement("span");
    details.textContent = `${suggestion.exercise_name}: ${suggestion.current_target_added_weight_kg} -> ${suggestion.suggested_target_added_weight_kg} kg`;
    wrapper.append(checkbox, details);
    form.appendChild(wrapper);
  });
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Apply selected increases";
  form.appendChild(submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const acceptedExerciseIds = Array.from(form.querySelectorAll('input[type="checkbox"]')).filter((input) => input.checked).map((input) => Number(input.value));
    try {
      await apiPost("/personal/api/cycle/suggestions/apply", {
        accepted_exercise_ids: acceptedExerciseIds
      });
      await loadDashboard();
    } catch (error) {
      setToast(suggestions, errorMessage(error), true);
    }
  });
  suggestions.appendChild(form);
}
function line(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element;
}
loadDashboard();
