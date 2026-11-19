# My API Integration Assistant

AI-powered assistant that turns integration requirements into verified integration designs.
See [`docs/PLAN.md`](docs/PLAN.md) for the roadmap and [`docs/CHECKLIST.md`](docs/CHECKLIST.md) for progress.

## Prerequisites
- Python 3.12 or newer — https://www.python.org/downloads/
- Node.js 20 or newer (LTS) — https://nodejs.org/
- Git — https://git-scm.com/downloads

## Run the backend (terminal 1)
```bash
cd backend
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
uvicorn app.main:app --reload
```
Open http://localhost:8000/docs for interactive API docs.

Run tests: `python -m pytest`

## Run the frontend (terminal 2)
```bash
cd frontend
npm install
cp .env.local.example .env.local   # Windows: copy .env.local.example .env.local
npm run dev
```
Open http://localhost:3000 — the "Backend status" card should show a green dot.

## Daily use

**Get the latest code** (after Claude pushes a new milestone), in PowerShell:
```bash
cd C:\Projects\api-integration-assistant
git pull
```
If `backend/requirements.txt` changed, reinstall backend libraries (with `.venv` activated):
```bash
pip install -r requirements.txt
```
If `frontend/package.json` changed, run `npm install` in `frontend`.

**Start the app** — two PowerShell tabs:
- Tab 1: `cd backend` → `.venv\Scripts\Activate.ps1` → `uvicorn app.main:app --reload`
- Tab 2: `cd frontend` → `npm run dev`

**Stop the app:** press `Ctrl + C` in each tab.

Your data lives in `backend/data/app.db`. Deleting that file resets the app to the three starter projects.
