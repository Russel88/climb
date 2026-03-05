export interface WeekPlanDto {
  weekNo: number;
  sets: number;
  targetReps: number;
  targetPercent: number;
}

export interface ExerciseDto {
  id: number;
  name: string;
  kind: 'progressive' | 'non_progressive';
  loadKind: 'external' | 'bodyweight_external' | null;
  targetAddedWeightKg: number | null;
  incrementStepKg: number | null;
  roundingStepKg: number | null;
  isActive: boolean;
  weekPlan: WeekPlanDto[];
}

export interface WorkoutTaskDto {
  session_item_id: number;
  exercise_id: number;
  exercise_name: string;
  kind: 'progressive' | 'non_progressive';
  set_index: number;
  planned_reps: number | null;
  planned_weight_kg: number | null;
}

export interface WorkoutSessionDto {
  id: number;
  session_date: string;
  mode: 'sequential' | 'interleaved';
  source: 'template' | 'ad_hoc';
  cycle_number: number;
  cycle_week: number;
  bodyweight_kg: number | null;
  next_task_index: number;
  task_count: number;
  current_task: WorkoutTaskDto | null;
}

export interface CycleStateDto {
  anchor_monday: string;
  current_monday: string;
  cycle_number: number;
  cycle_week: number;
  should_prompt_suggestions: boolean;
}

export interface CycleSuggestionDto {
  exercise_id: number;
  exercise_name: string;
  current_target_added_weight_kg: number;
  increment_step_kg: number;
  suggested_target_added_weight_kg: number;
}

export interface HistoryExercisePointDto {
  date: string;
  performed_at: string;
  set_index: number;
  planned_reps: number;
  actual_reps: number;
  planned_weight_kg: number;
  cycle_number: number;
  cycle_week: number;
}

export interface MonthDaySummaryDto {
  date: string;
  exercise_names: string[];
  has_note: boolean;
  note: string | null;
}

export interface DailyNoteDto {
  date: string;
  note_text: string | null;
  has_note: boolean;
}
