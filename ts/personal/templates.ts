import { apiDelete, apiGet, apiPost, apiPut, errorMessage, setToast } from './api-client';

interface ExerciseRecord {
  id: number;
  name: string;
  kind: string;
}

interface TemplateItem {
  exercise_id: number;
  exercise_name: string;
}

interface TemplateRecord {
  id: number;
  name: string;
  items: TemplateItem[];
}

interface ExerciseSelection {
  checked: boolean;
  exerciseId: number;
  position: number;
}

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

const templateForm = mustElement<HTMLFormElement>('templateForm');
const templateRecordId = mustElement<HTMLInputElement>('templateRecordId');
const templateName = mustElement<HTMLInputElement>('templateName');
const templateExerciseList = mustElement<HTMLDivElement>('templateExerciseList');
const templateList = mustElement<HTMLDivElement>('templateList');
const templateFormReset = mustElement<HTMLButtonElement>('templateFormReset');

let exercises: ExerciseRecord[] = [];
let templates: TemplateRecord[] = [];

function renderExerciseSelector(selectedExerciseIds: number[] = []): void {
  templateExerciseList.innerHTML = '';

  exercises.forEach((exercise, index) => {
    const row = document.createElement('div');
    row.className = 'item-row selector-row';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = String(exercise.id);
    checkbox.checked = selectedExerciseIds.includes(exercise.id);
    checkbox.className = 'selector-check';

    const position = document.createElement('input');
    position.type = 'number';
    position.min = '1';
    position.value = String(
      selectedExerciseIds.includes(exercise.id)
        ? selectedExerciseIds.indexOf(exercise.id) + 1
        : index + 1,
    );
    position.className = 'selector-position';
    position.dataset.role = 'position';

    const text = document.createElement('span');
    text.className = 'selector-label';
    text.textContent = `${exercise.name} (${exercise.kind})`;

    row.append(checkbox, text, position);
    templateExerciseList.appendChild(row);
  });
}

function selectedExerciseIds(): number[] {
  const selection: ExerciseSelection[] = Array.from(templateExerciseList.querySelectorAll<HTMLDivElement>('.item-row'))
    .map((row) => {
      const checkbox = row.querySelector<HTMLInputElement>('input[type="checkbox"]');
      const position = row.querySelector<HTMLInputElement>('input[data-role="position"]');
      return {
        checked: Boolean(checkbox?.checked),
        exerciseId: Number(checkbox?.value ?? 0),
        position: Number(position?.value || 0),
      };
    });

  return selection
    .filter((entry) => entry.checked)
    .sort((a, b) => a.position - b.position)
    .map((entry) => entry.exerciseId);
}

function resetForm(): void {
  templateRecordId.value = '';
  templateName.value = '';
  renderExerciseSelector();
}

function editTemplate(template: TemplateRecord): void {
  templateRecordId.value = String(template.id);
  templateName.value = template.name;
  renderExerciseSelector(template.items.map((item) => item.exercise_id));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderTemplates(): void {
  templateList.innerHTML = '';

  templates.forEach((template) => {
    const row = document.createElement('div');
    row.className = 'item-row';

    const details = document.createElement('div');
    const names = template.items.map((item) => item.exercise_name).join(' -> ');
    details.innerHTML = `<strong>${template.name}</strong><br><small>${names}</small>`;

    const actions = document.createElement('div');
    actions.className = 'item-actions';

    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'secondary';
    editButton.textContent = 'Edit';
    editButton.addEventListener('click', () => editTemplate(template));

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'danger';
    deleteButton.textContent = 'Delete';
    deleteButton.addEventListener('click', async () => {
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

async function loadData(): Promise<void> {
  const [exerciseResult, templateResult] = await Promise.all([
    apiGet<ExerciseRecord[]>('/personal/api/exercises'),
    apiGet<TemplateRecord[]>('/personal/api/templates'),
  ]);

  exercises = exerciseResult;
  templates = templateResult;
  renderExerciseSelector(selectedExerciseIds());
  renderTemplates();
}

templateForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const payload = {
    name: templateName.value.trim(),
    exercise_ids: selectedExerciseIds(),
  };

  try {
    if (templateRecordId.value) {
      await apiPut(`/personal/api/templates/${templateRecordId.value}`, payload);
    } else {
      await apiPost('/personal/api/templates', payload);
    }

    resetForm();
    await loadData();
  } catch (error) {
    setToast(templateList, errorMessage(error), true);
  }
});

templateFormReset.addEventListener('click', resetForm);

loadData().catch((error) => setToast(templateList, errorMessage(error), true));
