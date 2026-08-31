import { apiGet, apiPost, errorMessage, setToast } from './api-client';

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

const bodyweightForm = mustElement<HTMLFormElement>('bodyweightForm');
const manualBodyweight = mustElement<HTMLInputElement>('manualBodyweight');
const bodyweightStatus = mustElement<HTMLDivElement>('bodyweightStatus');

async function loadBodyweight(): Promise<void> {
  const payload = await apiGet<BodyweightLatest>('/personal/api/bodyweight/latest');
  if (payload.bodyweight_kg != null) {
    manualBodyweight.value = String(payload.bodyweight_kg);
    const loggedDate = payload.measured_at ? payload.measured_at.slice(0, 10) : '';
    setToast(bodyweightStatus, `Latest: ${payload.bodyweight_kg} kg${loggedDate ? ` (${loggedDate})` : ''}`);
  }
}

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

loadBodyweight().catch((error) => setToast(bodyweightStatus, errorMessage(error), true));
