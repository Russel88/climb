# AGENTS.md

This repository uses the Codex Workflow System.

## Project Overview

climb - Climbing wall and personal training app built with Flask, PostgreSQL, SQLAlchemy/Alembic, and TypeScript frontend bundles.

## Workflow Layout

- Project-local workflow metadata lives in `.codex-workflow/`
- Workflow commands live in the installed Codex plugin as `workflow-*` skills
- Workflow orchestration lives in the installed Codex plugin as `workflow-task-*` skills
- Planning state lives in `docs/planning/`
- Product and architecture knowledge lives in `knowledge/`

## How To Use The Workflow

Codex uses plugin skills instead of repo-local slash commands.

Examples:

- "Start a workflow session for this repo"
- "Use the workflow router and tell me what workflow operations are available"
- "Run workflow-implement-feature for user profile management"
- "Use workflow-review-code on my current changes"

## Development Guidance

### Code Style

- Follow the established patterns in the codebase
- Keep functions focused and easy to test
- Prefer explicit, readable code over clever shortcuts

### Documentation Rules

- Planning files belong in `docs/planning/`
- Technical specs belong in `docs/specs/`
- Reports belong in `docs/reports/`
- Product requirements belong in `knowledge/prd/`
- Architecture notes belong in `knowledge/architecture/`

### Validation Rules

- Run the smallest relevant test or verification command after edits
- Preserve user changes in existing workflow files unless replacement was requested
- Keep workflow-generated guidance in sync with the actual repository layout

## Environment Notes

### Prerequisites

- Python 3 with the packages from `requirements.txt`
- Node.js and npm for rebuilding bundled frontend assets
- PostgreSQL available via `PERSONAL_DATABASE_URL` for the `/personal` app

### Installation

```bash
pip install -r requirements.txt
npm install
export PERSONAL_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/climb_personal'
alembic upgrade head
```

### Development

```bash
python wsgi.py
```

### Tests

```bash
python -m unittest discover tests
```

### Build

```bash
npm run build
```

## Additional Context

- Backend code lives in `flaskapp/`
- Personal training frontend source lives in `ts/personal/`
- Bundled personal frontend assets are emitted to `flaskapp/static/personal/js/`
- Personal routes are served under `/personal` with API endpoints under `/personal/api`
