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

- Fixed 4-week cycle
- Monday-Sunday week boundaries
- Cycle reset anchors week 1 to current Monday
- Per-exercise week percentages (`personal_exercise_week_plan`)
