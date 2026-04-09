import { apiDelete, apiGet, apiPost, apiPut, errorMessage, setToast } from './api-client';

interface WeekPlanEntry {
  week_no: number;
  sets: number;
  target_reps?: number;
  target_reps_list: number[];
  target_percent?: number;
  target_percents: number[];
}

interface ExerciseRecord {
  id: number;
  name: string;
  kind: 'progressive' | 'non_progressive';
  load_kind: 'external' | 'bodyweight_external' | null;
  target_added_weight_kg: number | null;
  increment_step_kg: number | null;
  rounding_step_kg: number | null;
  week_plan: WeekPlanEntry[];
}

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

function mustInput(selector: string): HTMLInputElement {
  const input = weekPlanGrid.querySelector<HTMLInputElement>(selector);
  if (!input) {
    throw new Error(`Missing input ${selector}`);
  }
  return input;
}

const form = mustElement<HTMLFormElement>('exerciseForm');
const exerciseList = mustElement<HTMLDivElement>('exerciseList');
const exerciseIdInput = mustElement<HTMLInputElement>('exerciseId');
const nameInput = mustElement<HTMLInputElement>('name');
const kindSelect = mustElement<HTMLSelectElement>('kind');
const loadKindWrap = mustElement<HTMLLabelElement>('loadKindWrap');
const loadKindSelect = mustElement<HTMLSelectElement>('loadKind');
const targetWeightInput = mustElement<HTMLInputElement>('targetWeight');
const incrementStepInput = mustElement<HTMLInputElement>('incrementStep');
const roundingStepInput = mustElement<HTMLInputElement>('roundingStep');
const weekPlanGrid = mustElement<HTMLDivElement>('weekPlanGrid');
const resetButton = mustElement<HTMLButtonElement>('resetExerciseForm');

let cachedExercises: ExerciseRecord[] = [];

const DEFAULT_WEEK_PERCENTS: Record<number, number[]> = {
  1: [40, 50, 60, 65, 75, 85],
  2: [40, 50, 60, 70, 80, 90],
  3: [40, 50, 60, 75, 85, 95],
  4: [40, 40, 50, 50, 60, 60],
};
const DEFAULT_WEEK_REPS: Record<number, number[]> = {
  1: [5, 5, 5, 5, 5, 5],
  2: [5, 5, 5, 3, 3, 3],
  3: [5, 5, 5, 5, 3, 1],
  4: [5, 5, 5, 5, 5, 5],
};

function renderWeekPlanInputs(): void {
  weekPlanGrid.innerHTML = '';
  for (let week = 1; week <= 4; week += 1) {
    const wrapper = document.createElement('div');
    wrapper.className = 'item-row';
    const defaults = DEFAULT_WEEK_PERCENTS[week];
    const defaultReps = DEFAULT_WEEK_REPS[week];

    wrapper.innerHTML = `
      <div>
        <strong>Week ${week}</strong>
        <label>Sets<input type="number" min="1" step="1" data-week="${week}" data-field="sets" value="6"></label>
        <label>Set reps list<input type="text" data-week="${week}" data-field="target_reps_list" value="${defaultReps.join(', ')}"></label>
        <label>Set % list<input type="text" data-week="${week}" data-field="target_percents" value="${defaults.join(', ')}"></label>
      </div>
    `;

    weekPlanGrid.appendChild(wrapper);
  }
}

function toggleProgressiveFields(): void {
  const progressive = kindSelect.value === 'progressive';
  document.querySelectorAll<HTMLElement>('.progressive-only').forEach((node) => {
    node.classList.toggle('hidden', !progressive);
  });
  loadKindWrap.classList.toggle('hidden', !progressive);
}

function clearForm(): void {
  exerciseIdInput.value = '';
  nameInput.value = '';
  kindSelect.value = 'progressive';
  kindSelect.disabled = false;
  loadKindSelect.value = 'external';
  targetWeightInput.value = '';
  incrementStepInput.value = '';
  roundingStepInput.value = '';
  renderWeekPlanInputs();
  toggleProgressiveFields();
}

function weekPlanFromInputs(): WeekPlanEntry[] {
  const result: WeekPlanEntry[] = [];
  for (let week = 1; week <= 4; week += 1) {
    const sets = Number(mustInput(`[data-week="${week}"][data-field="sets"]`).value);
    const repsRaw = mustInput(`[data-week="${week}"][data-field="target_reps_list"]`).value;
    const targetRepsList = repsRaw
      .split(/[,\s]+/)
      .map((value) => value.trim())
      .filter((value) => value.length > 0)
      .map((value) => Number(value));
    const percentsRaw = mustInput(`[data-week="${week}"][data-field="target_percents"]`).value;
    const targetPercents = percentsRaw
      .split(/[,\s]+/)
      .map((value) => value.trim())
      .filter((value) => value.length > 0)
      .map((value) => Number(value));

    result.push({
      week_no: week,
      sets,
      target_reps_list: targetRepsList,
      target_percents: targetPercents,
    });
  }
  return result;
}

function payloadFromForm(): Record<string, unknown> {
  const kind = kindSelect.value;
  const payload: Record<string, unknown> = {
    name: nameInput.value.trim(),
    kind,
    is_active: true,
  };

  if (kind === 'progressive') {
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

function fillForm(exercise: ExerciseRecord): void {
  exerciseIdInput.value = String(exercise.id);
  nameInput.value = exercise.name;
  kindSelect.value = exercise.kind;
  kindSelect.disabled = true;
  toggleProgressiveFields();

  if (exercise.kind === 'progressive') {
    loadKindSelect.value = exercise.load_kind || 'external';
    targetWeightInput.value = String(exercise.target_added_weight_kg ?? '');
    incrementStepInput.value = String(exercise.increment_step_kg ?? '');
    roundingStepInput.value = String(exercise.rounding_step_kg ?? '');

    weekPlanGrid.querySelectorAll<HTMLInputElement>('input').forEach((input) => {
      input.value = '';
    });

    exercise.week_plan.forEach((week) => {
      mustInput(`[data-week="${week.week_no}"][data-field="sets"]`).value = String(week.sets);
      const reps = week.target_reps_list?.length
        ? week.target_reps_list
        : [week.target_reps ?? 0];
      mustInput(`[data-week="${week.week_no}"][data-field="target_reps_list"]`).value = reps.join(', ');
      const percents = week.target_percents?.length
        ? week.target_percents
        : [week.target_percent ?? 0];
      mustInput(`[data-week="${week.week_no}"][data-field="target_percents"]`).value = percents.join(', ');
    });
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderExerciseList(): void {
  exerciseList.innerHTML = '';
  cachedExercises.forEach((exercise) => {
    const row = document.createElement('div');
    row.className = 'item-row';

    const details = document.createElement('div');
    details.innerHTML = `<strong>${exercise.name}</strong><br><small>${exercise.kind}</small>`;

    const actions = document.createElement('div');
    actions.className = 'item-actions';

    const edit = document.createElement('button');
    edit.className = 'secondary';
    edit.type = 'button';
    edit.textContent = 'Edit';
    edit.addEventListener('click', () => fillForm(exercise));

    const remove = document.createElement('button');
    remove.className = 'danger';
    remove.type = 'button';
    remove.textContent = 'Delete';
    remove.addEventListener('click', async () => {
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

async function loadExercises(): Promise<void> {
  cachedExercises = await apiGet<ExerciseRecord[]>('/personal/api/exercises');
  renderExerciseList();
}

kindSelect.addEventListener('change', toggleProgressiveFields);
resetButton.addEventListener('click', clearForm);

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const payload = payloadFromForm();
    const id = exerciseIdInput.value;
    if (id) {
      await apiPut(`/personal/api/exercises/${id}`, payload);
    } else {
      await apiPost('/personal/api/exercises', payload);
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
