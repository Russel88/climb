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
var suggestions = mustElement("suggestions");
var weeklyExerciseStatus = mustElement("weeklyExerciseStatus");
async function loadDashboard() {
  try {
    const [weeklyStatus, suggestionPayload] = await Promise.all([
      apiGet("/personal/api/dashboard/week-exercises"),
      apiGet("/personal/api/cycle/suggestions")
    ]);
    renderWeeklyExerciseStatus(weeklyStatus);
    renderSuggestions(suggestionPayload.suggestions || []);
  } catch (error) {
    setToast(weeklyExerciseStatus, errorMessage(error), true);
  }
}
function renderWeeklyExerciseStatus(status) {
  weeklyExerciseStatus.innerHTML = "";
  weeklyExerciseStatus.appendChild(line(`${status.week_start} to ${status.week_end}`));
  weeklyExerciseStatus.appendChild(exerciseGroup("Logged", status.logged));
  weeklyExerciseStatus.appendChild(exerciseGroup("Not logged", status.not_logged));
}
function weekLabel(exercise) {
  if (exercise.cycle_week == null) {
    return exercise.kind.replace("_", " ");
  }
  return `Week ${exercise.cycle_week}/${exercise.cycle_weeks ?? 4}`;
}
function cycleLabel(exercise) {
  if (exercise.cycle_number == null) {
    return "";
  }
  return `cycle ${exercise.cycle_number}`;
}
function statusExplanation(exercise) {
  if (exercise.cycle_week == null) {
    return "Not a progressive exercise";
  }
  if (exercise.week_requirement_met) {
    return exercise.next_week_no === 1 ? `Week ${exercise.cycle_week} done, next cycle starts Monday` : `Week ${exercise.cycle_week} done, week ${exercise.next_week_no} from Monday`;
  }
  return `Week ${exercise.cycle_week} still open, restarts at week 1 on Monday if not completed`;
}
function exerciseGroup(title, exercises) {
  const group = document.createElement("div");
  group.className = "stack";
  const heading = document.createElement("h3");
  heading.textContent = title;
  group.appendChild(heading);
  if (!exercises.length) {
    group.appendChild(line("None"));
    return group;
  }
  exercises.forEach((exercise) => {
    const row = document.createElement("div");
    row.className = "item-row";
    const summary = document.createElement("span");
    summary.className = "exercise-status-name";
    const statusDot = document.createElement("span");
    const statusClass = exercise.kind === "non_progressive" ? "is-not-progressive" : exercise.week_requirement_met ? "is-on-track" : "is-off-track";
    statusDot.className = `increase-status-dot ${statusClass}`;
    statusDot.title = statusExplanation(exercise);
    const name = document.createElement("strong");
    name.textContent = exercise.name;
    const meta = document.createElement("span");
    meta.className = "exercise-cycle-meta";
    const badge = document.createElement("span");
    badge.className = exercise.cycle_week == null ? "week-badge is-muted" : "week-badge";
    badge.textContent = weekLabel(exercise);
    badge.title = statusExplanation(exercise);
    meta.appendChild(badge);
    const cycle = cycleLabel(exercise);
    if (cycle) {
      const cycleText = document.createElement("small");
      cycleText.textContent = cycle;
      meta.appendChild(cycleText);
    }
    summary.append(statusDot, name);
    row.append(summary, meta);
    group.appendChild(row);
  });
  return group;
}
function renderSuggestions(list) {
  suggestions.innerHTML = "";
  if (!list.length) {
    suggestions.appendChild(line("No exercise has finished a cycle awaiting review."));
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
    details.textContent = `${suggestion.exercise_name} (cycle ${suggestion.completed_cycle_number} done): ${suggestion.current_target_added_weight_kg} -> ${suggestion.suggested_target_added_weight_kg} kg`;
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
