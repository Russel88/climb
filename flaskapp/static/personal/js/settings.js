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
var bodyweightForm = mustElement("bodyweightForm");
var manualBodyweight = mustElement("manualBodyweight");
var bodyweightStatus = mustElement("bodyweightStatus");
async function loadBodyweight() {
  const payload = await apiGet("/personal/api/bodyweight/latest");
  if (payload.bodyweight_kg != null) {
    manualBodyweight.value = String(payload.bodyweight_kg);
    const loggedDate = payload.measured_at ? payload.measured_at.slice(0, 10) : "";
    setToast(bodyweightStatus, `Latest: ${payload.bodyweight_kg} kg${loggedDate ? ` (${loggedDate})` : ""}`);
  }
}
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
loadBodyweight().catch((error) => setToast(bodyweightStatus, errorMessage(error), true));
