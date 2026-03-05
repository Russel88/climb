import { apiGet, apiPost, errorMessage, setToast } from './api-client';

interface CycleState {
  cycle_number: number;
  cycle_week: number;
  anchor_monday: string;
  should_prompt_suggestions: boolean;
}

interface CycleSuggestion {
  exercise_id: number;
  exercise_name: string;
  current_target_added_weight_kg: number;
  suggested_target_added_weight_kg: number;
}

interface SuggestionsResponse {
  suggestions: CycleSuggestion[];
}

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

const cycleStatus = mustElement<HTMLDivElement>('cycleStatus');
const suggestions = mustElement<HTMLDivElement>('suggestions');

async function loadDashboard(): Promise<void> {
  try {
    const state = await apiGet<CycleState>('/personal/api/cycle/state');
    cycleStatus.innerHTML = '';
    cycleStatus.appendChild(line(`Cycle number: ${state.cycle_number}`));
    cycleStatus.appendChild(line(`Cycle week: ${state.cycle_week}`));
    cycleStatus.appendChild(line(`Week 1 anchor Monday: ${state.anchor_monday}`));

    if (!state.should_prompt_suggestions) {
      suggestions.innerHTML = '';
      suggestions.appendChild(line('No pending cycle increase suggestions.'));
      return;
    }

    const suggestionPayload = await apiGet<SuggestionsResponse>('/personal/api/cycle/suggestions');
    renderSuggestions(suggestionPayload.suggestions || []);
  } catch (error) {
    setToast(cycleStatus, errorMessage(error), true);
  }
}

function renderSuggestions(list: CycleSuggestion[]): void {
  suggestions.innerHTML = '';

  if (!list.length) {
    suggestions.appendChild(line('No exercises qualify for increase this cycle.'));

    const markButton = document.createElement('button');
    markButton.textContent = 'Mark reviewed';
    markButton.addEventListener('click', async () => {
      try {
        await apiPost('/personal/api/cycle/suggestions/apply', { accepted_exercise_ids: [] });
        await loadDashboard();
      } catch (error) {
        setToast(suggestions, errorMessage(error), true);
      }
    });
    suggestions.appendChild(markButton);
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
    details.textContent = `${suggestion.exercise_name}: ${suggestion.current_target_added_weight_kg} -> ${suggestion.suggested_target_added_weight_kg} kg`;

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

loadDashboard();
