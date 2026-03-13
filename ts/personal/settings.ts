import { apiGet, apiPost, errorMessage, setToast } from './api-client';

interface CycleState {
  cycle_number: number;
  cycle_week: number;
  anchor_monday: string;
}

interface BodyweightLatest {
  bodyweight_kg: number | null;
  measured_at?: string;
}

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

const settingsCycleStatus = mustElement<HTMLDivElement>('settingsCycleStatus');
const resetCycleButton = mustElement<HTMLButtonElement>('resetCycle');
const bodyweightForm = mustElement<HTMLFormElement>('bodyweightForm');
const manualBodyweight = mustElement<HTMLInputElement>('manualBodyweight');
const bodyweightStatus = mustElement<HTMLDivElement>('bodyweightStatus');

async function loadCycle(): Promise<void> {
  const state = await apiGet<CycleState>('/personal/api/cycle/state');
  settingsCycleStatus.innerHTML = '';
  settingsCycleStatus.appendChild(line(`Cycle: ${state.cycle_number}`));
  settingsCycleStatus.appendChild(line(`Week: ${state.cycle_week}`));
  settingsCycleStatus.appendChild(line(`Anchor Monday: ${state.anchor_monday}`));
}

async function loadBodyweight(): Promise<void> {
  const payload = await apiGet<BodyweightLatest>('/personal/api/bodyweight/latest');
  if (payload.bodyweight_kg != null) {
    manualBodyweight.value = String(payload.bodyweight_kg);
    const loggedDate = payload.measured_at ? payload.measured_at.slice(0, 10) : '';
    setToast(bodyweightStatus, `Latest: ${payload.bodyweight_kg} kg${loggedDate ? ` (${loggedDate})` : ''}`);
  }
}

function line(text: string): HTMLDivElement {
  const element = document.createElement('div');
  element.textContent = text;
  return element;
}

resetCycleButton.addEventListener('click', async () => {
  if (!window.confirm('Reset cycle to this week Monday and start week 1?')) {
    return;
  }

  try {
    await apiPost('/personal/api/cycle/reset', {});
    await loadCycle();
  } catch (error) {
    setToast(settingsCycleStatus, errorMessage(error), true);
  }
});

bodyweightForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  try {
    const value = Number(manualBodyweight.value);
    await apiPost('/personal/api/bodyweight', { bodyweight_kg: value });
    await loadBodyweight();
  } catch (error) {
    setToast(bodyweightStatus, errorMessage(error), true);
  }
});

loadCycle().catch((error) => setToast(settingsCycleStatus, errorMessage(error), true));
loadBodyweight().catch((error) => setToast(bodyweightStatus, errorMessage(error), true));
