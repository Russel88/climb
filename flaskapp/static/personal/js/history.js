// ts/personal/api-client.ts
async function apiGet(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
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

// ts/personal/history.ts
function mustElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}
var historyExercise = mustElement("historyExercise");
var historyFilterForm = mustElement("historyFilterForm");
var historyRangeType = mustElement("historyRangeType");
var historyRangeValue = mustElement("historyRangeValue");
var historyResult = mustElement("historyResult");
var monthFilterForm = mustElement("monthFilterForm");
var monthYear = mustElement("monthYear");
var monthMonth = mustElement("monthMonth");
var monthCalendar = mustElement("monthCalendar");
var noteForm = mustElement("noteForm");
var noteDate = mustElement("noteDate");
var noteText = mustElement("noteText");
function setCurrentMonthInputs() {
  const now = /* @__PURE__ */ new Date();
  monthYear.value = String(now.getFullYear());
  monthMonth.value = String(now.getMonth() + 1);
  noteDate.value = now.toISOString().slice(0, 10);
}
function renderExercises(exercises) {
  historyExercise.innerHTML = "";
  exercises.forEach((exercise) => {
    const option = document.createElement("option");
    option.value = String(exercise.id);
    option.textContent = exercise.name;
    historyExercise.appendChild(option);
  });
}
function renderExerciseHistory(payload) {
  historyResult.innerHTML = "";
  historyResult.appendChild(line(`From ${payload.start_date} to ${payload.end_date}`));
  if (payload.progressive_logs.length) {
    const maxByDay = /* @__PURE__ */ new Map();
    payload.progressive_logs.forEach((log) => {
      if (log.actual_reps <= 0) {
        return;
      }
      const current = maxByDay.get(log.date);
      if (!current || log.planned_weight_kg > current.planned_weight_kg || log.planned_weight_kg === current.planned_weight_kg && log.actual_reps > current.actual_reps) {
        maxByDay.set(log.date, log);
      }
    });
    Array.from(maxByDay.values()).forEach((log) => {
      historyResult.appendChild(
        line(
          `${log.date}: max ${log.planned_weight_kg} kg, target ${log.planned_reps}, actual ${log.actual_reps}`
        )
      );
    });
  }
  if (payload.non_progressive_logs.length) {
    payload.non_progressive_logs.forEach((log) => {
      const setText = (log.set_count ?? 1) > 1 ? ` (${log.set_count} sets)` : "";
      historyResult.appendChild(line(`${log.date}: completed${setText}${log.note ? ` - ${log.note}` : ""}`));
    });
  }
  if (!payload.progressive_logs.length && !payload.non_progressive_logs.length) {
    historyResult.appendChild(line("No records in selected range."));
  }
}
function renderMonth(payload) {
  monthCalendar.innerHTML = "";
  if (!payload.days.length) {
    monthCalendar.appendChild(line("No sessions or notes in this month."));
    return;
  }
  payload.days.forEach((day) => {
    const card = document.createElement("div");
    card.className = "calendar-day";
    const dateLabel = document.createElement("strong");
    dateLabel.textContent = day.date;
    card.appendChild(dateLabel);
    if (day.exercise_names.length) {
      const list = document.createElement("div");
      list.textContent = day.exercise_names.join(", ");
      card.appendChild(list);
    } else {
      card.appendChild(line("No exercises"));
    }
    if (day.has_note) {
      const noteRow = document.createElement("div");
      const icon = document.createElement("span");
      icon.className = "note-icon";
      icon.textContent = "i";
      icon.title = day.note || "";
      const noteTextElement = document.createElement("div");
      noteTextElement.className = "hidden";
      noteTextElement.textContent = day.note || "";
      icon.addEventListener("click", () => {
        noteTextElement.classList.toggle("hidden");
      });
      noteRow.append(icon, noteTextElement);
      card.appendChild(noteRow);
    }
    monthCalendar.appendChild(card);
  });
}
function line(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element;
}
async function loadExercises() {
  const exercises = await apiGet("/personal/api/exercises");
  renderExercises(exercises);
}
async function loadExerciseHistory() {
  const exerciseId = Number(historyExercise.value);
  const rangeType = historyRangeType.value;
  const value = Number(historyRangeValue.value);
  const payload = await apiGet(
    `/personal/api/history/exercises/${exerciseId}?range_type=${encodeURIComponent(rangeType)}&value=${value}`
  );
  renderExerciseHistory(payload);
}
async function loadMonth() {
  const payload = await apiGet(
    `/personal/api/history/month?year=${encodeURIComponent(monthYear.value)}&month=${encodeURIComponent(monthMonth.value)}`
  );
  renderMonth(payload);
}
historyFilterForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await loadExerciseHistory();
  } catch (error) {
    setToast(historyResult, errorMessage(error), true);
  }
});
monthFilterForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await loadMonth();
  } catch (error) {
    setToast(monthCalendar, errorMessage(error), true);
  }
});
noteForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await fetch(`/personal/api/notes/${encodeURIComponent(noteDate.value)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ note_text: noteText.value })
    }).then(async (response) => {
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || "Failed to save note");
      }
      return payload;
    });
    noteText.value = "";
    await loadMonth();
  } catch (error) {
    setToast(monthCalendar, errorMessage(error), true);
  }
});
setCurrentMonthInputs();
loadExercises().then(loadExerciseHistory).catch((error) => setToast(historyResult, errorMessage(error), true));
loadMonth().catch((error) => setToast(monthCalendar, errorMessage(error), true));
