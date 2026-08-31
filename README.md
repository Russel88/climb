# Climb + Personal Training App

This repository now contains:

- Existing climbing wall app at `/`
- New personal training app at `/personal`

## Tech stack

- Backend: Flask (Python)
- Personal app DB: PostgreSQL (`PERSONAL_DATABASE_URL`)
- ORM: SQLAlchemy
- Migrations: Alembic
- Frontend modules: TypeScript source (`ts/personal`) with bundled JS output in `flaskapp/static/personal/js`

## Setup

1. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set personal PostgreSQL URL:

   ```bash
   export PERSONAL_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/climb_personal'
   ```

3. Run migrations:

   ```bash
   alembic upgrade head
   ```

4. Optional frontend build (JS is already committed, but rebuild after TS changes):

   ```bash
   npm install
   npm run build
   ```

5. Run app:

   ```bash
   python wsgi.py
   ```

## Personal app routes

- UI: `/personal`
- API prefix: `/personal/api`

Main UI pages:

- `/personal`
- `/personal/exercises`
- `/personal/templates`
- `/personal/workouts/new`
- `/personal/history`
- `/personal/settings`

## Cycle behavior

Every exercise runs its own 4-week cycle. Exercises are never synchronised with each
other, and there is nothing to reset by hand: the position is derived from the logs.

- Monday-Sunday week boundaries
- An exercise moves to the next week when its heaviest set of the week is completed for
  the target reps; week 4 rolls into week 1 of the next cycle
- A week that is missed, or logged below the target, sends the exercise back to week 1
  from the following Monday
- Per-exercise week percentages (`personal_exercise_week_plan`)
- Cycle position is not stored. It is replayed from the week and cycle already stamped on
  every row of `personal_set_log`, so existing training data carries an in-flight cycle
  straight over
- Finishing a full cycle offers a target weight increase on the dashboard, tracked per
  exercise in `personal_exercise_cycle_review`

`personal_cycle_state` and `personal_cycle_review` held the old global cycle and are left
in place but no longer read.
