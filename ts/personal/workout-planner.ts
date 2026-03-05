import { apiGet, apiPost, errorMessage, setToast } from './api-client';

interface ExerciseRecord {
  id: number;
  name: string;
  kind: string;
}

interface TemplateRecord {
  id: number;
  name: string;
}

interface BodyweightResponse {
  bodyweight_kg: number | null;
}

interface PreviewTask {
  exercise_name: string;
  planned_weight_kg: number | null;
  planned_reps: number | null;
}

interface PreviewResponse {
  cycle_number: number;
  cycle_week: number;
  task_count: number;
  first_task: PreviewTask | null;
}

interface StartSessionResponse {
  id: number;
}

interface SessionPayload {
  source: string;
  mode: string;
  session_date: string;
  bodyweight_kg?: number;
  template_id?: number;
  exercise_ids?: number[];
}

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

const sourceSelect = mustElement<HTMLSelectElement>('sessionSource');
const templateWrap = mustElement<HTMLLabelElement>('templateWrap');
const templateIdSelect = mustElement<HTMLSelectElement>('templateId');
const modeSelect = mustElement<HTMLSelectElement>('sessionMode');
const dateInput = mustElement<HTMLInputElement>('sessionDate');
const bodyweightInput = mustElement<HTMLInputElement>('sessionBodyweight');
const exerciseSelectionWrap = mustElement<HTMLDivElement>('exerciseSelectionWrap');
const plannerExerciseList = mustElement<HTMLDivElement>('plannerExerciseList');
const previewButton = mustElement<HTMLButtonElement>('previewSession');
const startButton = mustElement<HTMLButtonElement>('startSession');
const previewPanel = mustElement<HTMLDivElement>('sessionPreview');

let exercises: ExerciseRecord[] = [];
let templates: TemplateRecord[] = [];

function setDefaultDate(): void {
  const now = new Date();
  const iso = now.toISOString().slice(0, 10);
  dateInput.value = iso;
}

function renderExerciseSelection(): void {
  plannerExerciseList.innerHTML = '';

  exercises.forEach((exercise, index) => {
    const row = document.createElement('div');
    row.className = 'item-row';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = String(exercise.id);

    const position = document.createElement('input');
    position.type = 'number';
    position.min = '1';
    position.value = String(index + 1);
    position.style.maxWidth = '4.5rem';
    position.dataset.role = 'position';

    const text = document.createElement('span');
    text.textContent = `${exercise.name} (${exercise.kind})`;

    row.append(checkbox, text, position);
    plannerExerciseList.appendChild(row);
  });
}

function renderTemplates(): void {
  templateIdSelect.innerHTML = '';
  templates.forEach((template) => {
    const option = document.createElement('option');
    option.value = String(template.id);
    option.textContent = template.name;
    templateIdSelect.appendChild(option);
  });
}

function selectedExerciseIds(): number[] {
  return Array.from(plannerExerciseList.querySelectorAll<HTMLDivElement>('.item-row'))
    .map((row) => {
      const checkbox = row.querySelector<HTMLInputElement>('input[type="checkbox"]');
      const position = row.querySelector<HTMLInputElement>('input[data-role="position"]');
      return {
        checked: Boolean(checkbox?.checked),
        exerciseId: Number(checkbox?.value ?? 0),
        position: Number(position?.value || 0),
      };
    })
    .filter((entry) => entry.checked)
    .sort((a, b) => a.position - b.position)
    .map((entry) => entry.exerciseId);
}

function buildPayload(): SessionPayload {
  const source = sourceSelect.value;
  const payload: SessionPayload = {
    source,
    mode: modeSelect.value,
    session_date: dateInput.value,
  };

  if (bodyweightInput.value.trim()) {
    payload.bodyweight_kg = Number(bodyweightInput.value);
  }

  if (source === 'template') {
    payload.template_id = Number(templateIdSelect.value);
  } else {
    payload.exercise_ids = selectedExerciseIds();
  }

  return payload;
}

function refreshSourceMode(): void {
  const isTemplate = sourceSelect.value === 'template';
  templateWrap.classList.toggle('hidden', !isTemplate);
  exerciseSelectionWrap.classList.toggle('hidden', isTemplate);
}

function renderPreview(data: PreviewResponse): void {
  previewPanel.innerHTML = '';
  previewPanel.appendChild(line(`Cycle ${data.cycle_number}, week ${data.cycle_week}`));
  previewPanel.appendChild(line(`Tasks: ${data.task_count}`));

  if (data.first_task) {
    previewPanel.appendChild(
      line(
        `First: ${data.first_task.exercise_name}${
          data.first_task.planned_weight_kg == null ? '' : `, ${data.first_task.planned_weight_kg} kg`
        }${data.first_task.planned_reps == null ? '' : `, ${data.first_task.planned_reps} reps`}`,
      ),
    );
  }
}

function line(text: string): HTMLDivElement {
  const element = document.createElement('div');
  element.textContent = text;
  return element;
}

async function loadData(): Promise<void> {
  const [exerciseData, templateData, bodyweightData] = await Promise.all([
    apiGet<ExerciseRecord[]>('/personal/api/exercises'),
    apiGet<TemplateRecord[]>('/personal/api/templates'),
    apiGet<BodyweightResponse>('/personal/api/bodyweight/latest'),
  ]);

  exercises = exerciseData;
  templates = templateData;

  renderExerciseSelection();
  renderTemplates();

  if (bodyweightData.bodyweight_kg != null) {
    bodyweightInput.value = String(bodyweightData.bodyweight_kg);
  }
}

sourceSelect.addEventListener('change', refreshSourceMode);

previewButton.addEventListener('click', async () => {
  try {
    const preview = await apiPost<PreviewResponse>('/personal/api/workout-sessions/preview', buildPayload());
    renderPreview(preview);
  } catch (error) {
    setToast(previewPanel, errorMessage(error), true);
  }
});

startButton.addEventListener('click', async () => {
  try {
    const session = await apiPost<StartSessionResponse>('/personal/api/workout-sessions', buildPayload());
    window.location.href = `/personal/workouts/${session.id}/run`;
  } catch (error) {
    setToast(previewPanel, errorMessage(error), true);
  }
});

setDefaultDate();
refreshSourceMode();
loadData().catch((error) => setToast(previewPanel, errorMessage(error), true));
