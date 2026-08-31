import { apiGet, apiPost, errorMessage, setToast } from './api-client';
import type { CycleSuggestionDto, WeeklyExerciseDto, WeeklyExerciseStatusDto } from './types';

interface SuggestionsResponse {
  suggestions: CycleSuggestionDto[];
}

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

const suggestions = mustElement<HTMLDivElement>('suggestions');
const weeklyExerciseStatus = mustElement<HTMLDivElement>('weeklyExerciseStatus');

// The two panels load independently: a failure in one must not blank the other.
async function loadWeeklyStatus(): Promise<void> {
  try {
    renderWeeklyExerciseStatus(await apiGet<WeeklyExerciseStatusDto>('/personal/api/dashboard/week-exercises'));
  } catch (error) {
    setToast(weeklyExerciseStatus, errorMessage(error), true);
  }
}

async function loadSuggestions(): Promise<void> {
  try {
    const payload = await apiGet<SuggestionsResponse>('/personal/api/cycle/suggestions');
    renderSuggestions(payload.suggestions || []);
  } catch (error) {
    setToast(suggestions, errorMessage(error), true);
  }
}

async function loadDashboard(): Promise<void> {
  await Promise.all([loadWeeklyStatus(), loadSuggestions()]);
}

function renderWeeklyExerciseStatus(status: WeeklyExerciseStatusDto): void {
  weeklyExerciseStatus.innerHTML = '';
  weeklyExerciseStatus.appendChild(line(`${status.week_start} to ${status.week_end}`));
  weeklyExerciseStatus.appendChild(exerciseGroup('Logged', status.logged));
  weeklyExerciseStatus.appendChild(exerciseGroup('Not logged', status.not_logged));
}

function weekLabel(exercise: WeeklyExerciseDto): string {
  if (exercise.cycle_week == null) {
    return exercise.kind.replace('_', ' ');
  }
  return `Week ${exercise.cycle_week}/${exercise.cycle_weeks ?? 4}`;
}

function targetLoadLabel(exercise: WeeklyExerciseDto): string {
  const target = exercise.target_added_weight_kg;
  if (target == null) {
    return '';
  }
  const rounded = Number(target.toFixed(2));
  return `${rounded} kg`;
}

function statusExplanation(exercise: WeeklyExerciseDto): string {
  if (exercise.cycle_week == null) {
    return 'Not a progressive exercise';
  }
  if (exercise.week_requirement_met) {
    return exercise.next_week_no === 1
      ? `Week ${exercise.cycle_week} done, next cycle starts Monday`
      : `Week ${exercise.cycle_week} done, week ${exercise.next_week_no} from Monday`;
  }
  return `Week ${exercise.cycle_week} still open, restarts at week 1 on Monday if not completed`;
}

function exerciseGroup(title: string, exercises: WeeklyExerciseDto[]): HTMLDivElement {
  const group = document.createElement('div');
  group.className = 'stack';

  const heading = document.createElement('h3');
  heading.textContent = title;
  group.appendChild(heading);

  if (!exercises.length) {
    group.appendChild(line('None'));
    return group;
  }

  exercises.forEach((exercise) => {
    const row = document.createElement('div');
    row.className = 'item-row';

    const summary = document.createElement('span');
    summary.className = 'exercise-status-name';

    const statusDot = document.createElement('span');
    const statusClass = exercise.kind === 'non_progressive'
      ? 'is-not-progressive'
      : exercise.week_requirement_met
        ? 'is-on-track'
        : 'is-off-track';
    statusDot.className = `increase-status-dot ${statusClass}`;
    statusDot.title = statusExplanation(exercise);

    const name = document.createElement('strong');
    name.textContent = exercise.name;

    const meta = document.createElement('span');
    meta.className = 'exercise-cycle-meta';

    const badge = document.createElement('span');
    badge.className = exercise.cycle_week == null ? 'week-badge is-muted' : 'week-badge';
    badge.textContent = weekLabel(exercise);
    badge.title = statusExplanation(exercise);
    meta.appendChild(badge);

    const targetLoad = targetLoadLabel(exercise);
    if (targetLoad) {
      const targetText = document.createElement('small');
      targetText.className = 'exercise-target-load';
      targetText.textContent = targetLoad;
      targetText.title = 'Target load';
      meta.appendChild(targetText);
    }

    summary.append(statusDot, name);
    row.append(summary, meta);
    group.appendChild(row);
  });

  return group;
}

function renderSuggestions(list: CycleSuggestionDto[]): void {
  suggestions.innerHTML = '';

  if (!list.length) {
    suggestions.appendChild(line('No exercise has finished a cycle awaiting review.'));
    return;
  }

  const form = document.createElement('form');
  form.className = 'stack';

  list.forEach((suggestion) => {
    const wrapper = document.createElement('label');
    wrapper.className = 'item-row';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = String(suggestion.exercise_id);
    checkbox.checked = true;

    const details = document.createElement('span');
    details.textContent = `${suggestion.exercise_name} (cycle ${suggestion.completed_cycle_number} done): ${suggestion.current_target_added_weight_kg} -> ${suggestion.suggested_target_added_weight_kg} kg`;

    wrapper.append(checkbox, details);
    form.appendChild(wrapper);
  });

  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.textContent = 'Apply selected increases';
  form.appendChild(submit);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const acceptedExerciseIds = Array.from(form.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'))
      .filter((input) => input.checked)
      .map((input) => Number(input.value));

    try {
      await apiPost('/personal/api/cycle/suggestions/apply', {
        accepted_exercise_ids: acceptedExerciseIds,
      });
      await loadDashboard();
    } catch (error) {
      setToast(suggestions, errorMessage(error), true);
    }
  });

  suggestions.appendChild(form);
}

function line(text: string): HTMLDivElement {
  const element = document.createElement('div');
  element.textContent = text;
  return element;
}

loadDashboard().catch((error) => setToast(weeklyExerciseStatus, errorMessage(error), true));
