export interface WeekPlanDto {
  weekNo: number;
  sets: number;
  targetReps: number;
  targetRepsList: number[];
  targetPercent: number;
  targetPercents: number[];
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
  cycle_week: number | null;
  cycle_number: number | null;
}

export interface WorkoutSessionDto {
  id: number;
  session_date: string;
  mode: 'sequential' | 'interleaved';
  source: 'template' | 'ad_hoc';
  bodyweight_kg: number | null;
  next_task_index: number;
  task_count: number;
  current_task: WorkoutTaskDto | null;
}

export interface ExerciseCycleDto {
  exercise_id: number;
  exercise_name: string;
  kind: 'progressive' | 'non_progressive';
  cycle_week: number | null;
  cycle_number: number | null;
  cycle_weeks: number | null;
  logged_this_week: boolean;
  is_restart: boolean;
}

export interface WeeklyExerciseDto {
  id: number;
  name: string;
  kind: 'progressive' | 'non_progressive';
  target_added_weight_kg: number | null;
  cycle_week: number | null;
  cycle_number: number | null;
  cycle_weeks: number | null;
  next_week_no: number | null;
  is_restart: boolean;
  week_requirement_met: boolean;
  on_track_for_cycle_increase: boolean;
}

export interface WeeklyExerciseStatusDto {
  week_start: string;
  week_end: string;
  cycle_weeks: number;
  logged: WeeklyExerciseDto[];
  not_logged: WeeklyExerciseDto[];
}

export interface CycleSuggestionDto {
  exercise_id: number;
  exercise_name: string;
  completed_cycle_number: number;
  cycle_week: number | null;
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
