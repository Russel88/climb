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

// ts/personal/settings.ts
function mustElement(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}
var settingsCycleStatus = mustElement("settingsCycleStatus");
var resetCycleButton = mustElement("resetCycle");
var bodyweightForm = mustElement("bodyweightForm");
var manualBodyweight = mustElement("manualBodyweight");
var bodyweightStatus = mustElement("bodyweightStatus");
async function loadCycle() {
  const state = await apiGet("/personal/api/cycle/state");
  settingsCycleStatus.innerHTML = "";
  settingsCycleStatus.appendChild(line(`Cycle: ${state.cycle_number}`));
  settingsCycleStatus.appendChild(line(`Week: ${state.cycle_week}`));
  settingsCycleStatus.appendChild(line(`Anchor Monday: ${state.anchor_monday}`));
}
async function loadBodyweight() {
  const payload = await apiGet("/personal/api/bodyweight/latest");
  if (payload.bodyweight_kg != null) {
    manualBodyweight.value = String(payload.bodyweight_kg);
    const loggedDate = payload.measured_at ? payload.measured_at.slice(0, 10) : "";
    setToast(bodyweightStatus, `Latest: ${payload.bodyweight_kg} kg${loggedDate ? ` (${loggedDate})` : ""}`);
  }
}
function line(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element;
}
resetCycleButton.addEventListener("click", async () => {
  if (!window.confirm("Reset cycle to this week Monday and start week 1?")) {
    return;
  }
  try {
    await apiPost("/personal/api/cycle/reset", {});
    await loadCycle();
  } catch (error) {
    setToast(settingsCycleStatus, errorMessage(error), true);
  }
});
bodyweightForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const value = Number(manualBodyweight.value);
    await apiPost("/personal/api/bodyweight", { bodyweight_kg: value });
    await loadBodyweight();
  } catch (error) {
    setToast(bodyweightStatus, errorMessage(error), true);
  }
});
loadCycle().catch((error) => setToast(settingsCycleStatus, errorMessage(error), true));
loadBodyweight().catch((error) => setToast(bodyweightStatus, errorMessage(error), true));
