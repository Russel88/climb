import { apiGet, apiPost, errorMessage, setToast } from './api-client';

interface WorkoutTask {
  kind: 'progressive' | 'non_progressive';
  exercise_name: string;
  planned_weight_kg: number | null;
  planned_reps: number | null;
}

interface WorkoutSession {
  id: number;
  next_task_index: number;
  task_count: number;
  current_task: WorkoutTask | null;
}

interface CompletePayload {
  actual_reps?: number;
  note?: string;
}

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

const sessionIdNode = mustElement<HTMLElement>('sessionId');
const taskCard = mustElement<HTMLDivElement>('taskCard');
const taskForm = mustElement<HTMLFormElement>('taskForm');
const repsWrap = mustElement<HTMLLabelElement>('repsWrap');
const noteWrap = mustElement<HTMLLabelElement>('noteWrap');
const actualRepsInput = mustElement<HTMLInputElement>('actualReps');
const taskNoteInput = mustElement<HTMLInputElement>('taskNote');
const finishSessionButton = mustElement<HTMLButtonElement>('finishSession');

const sessionId = Number(sessionIdNode.textContent);
let session: WorkoutSession | null = null;

function renderSession(): void {
  taskCard.innerHTML = '';

  if (!session) {
    taskCard.appendChild(line('Session not loaded.'));
    return;
  }

  taskCard.appendChild(line(`Task ${Math.min(session.next_task_index + 1, session.task_count)} of ${session.task_count}`));

  if (!session.current_task) {
    taskCard.appendChild(line('Workout complete.'));
    taskForm.classList.add('hidden');
    return;
  }

  taskForm.classList.remove('hidden');

  const task = session.current_task;
  const details = [task.exercise_name];
  if (task.planned_weight_kg != null) {
    details.push(`${task.planned_weight_kg} kg`);
  }
  if (task.planned_reps != null) {
    details.push(`${task.planned_reps} reps`);
  }

  taskCard.appendChild(line(details.join(' | ')));

  const progressive = task.kind === 'progressive';
  repsWrap.classList.toggle('hidden', !progressive);
  noteWrap.classList.toggle('hidden', progressive);
  actualRepsInput.value = '';
  taskNoteInput.value = '';
}

function line(text: string): HTMLDivElement {
  const element = document.createElement('div');
  element.textContent = text;
  return element;
}

async function loadSession(): Promise<void> {
  session = await apiGet<WorkoutSession>(`/personal/api/workout-sessions/${sessionId}`);
  renderSession();
}

taskForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  if (!session?.current_task) {
    return;
  }

  const payload: CompletePayload = {};
  if (session.current_task.kind === 'progressive') {
    payload.actual_reps = Number(actualRepsInput.value);
  } else if (taskNoteInput.value.trim()) {
    payload.note = taskNoteInput.value.trim();
  }

  try {
    session = await apiPost<WorkoutSession>(
      `/personal/api/workout-sessions/${session.id}/tasks/${session.next_task_index}/complete`,
      payload,
    );
    renderSession();
  } catch (error) {
    setToast(taskCard, errorMessage(error), true);
  }
});

finishSessionButton.addEventListener('click', async () => {
  try {
    session = await apiPost<WorkoutSession>(`/personal/api/workout-sessions/${sessionId}/finish`, {});
    renderSession();
  } catch (error) {
    setToast(taskCard, errorMessage(error), true);
  }
});

loadSession().catch((error) => setToast(taskCard, errorMessage(error), true));
