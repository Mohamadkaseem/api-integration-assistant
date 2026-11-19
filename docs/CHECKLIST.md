# Project Checklist

**Current state:** Milestone 2 built and verified in the build environment. Waiting for you to run it locally.

## M1 — Foundations ✅
- [x] Folders: `backend/`, `frontend/`, `docs/`
- [x] `.gitignore` excludes secrets and the local database
- [x] FastAPI backend, settings from `.env`
- [x] `GET /api/health` + 2 passing tests
- [x] Next.js + TypeScript + Tailwind UI with sidebar for all 9 features
- [x] Dashboard with live backend status
- [x] Research report (`docs/RESEARCH.md`) and plan (`docs/PLAN.md`)
- [x] Run locally on Windows: tests pass, green "Connected" dot

## M2 — Projects & SQLite ✅ (built & verified in the build environment)
- [x] SQLModel + SQLite database file (`backend/data/app.db`, not committed to Git)
- [x] Project model (name, source/target app, requirement, status, notes, timestamps)
- [x] API: list / create / view / edit / delete (`/api/projects`)
- [x] Projects A, B, C pre-loaded on first start (never overwrites your edits)
- [x] Tests use a throw-away in-memory database — 10 passing
- [x] Projects page, "New project" form, detail page with Edit and Delete (delete asks first)
- [x] Dashboard "Integration projects" count is real
- [x] Fixed test warning (httpx → httpx2)
- [ ] **You:** `git pull`, install new libraries, restart, try create/edit/delete

## M3 — AI + Requirement Analyzer
## M4 — Request Builder & API testing
## M5 — Credentials & Auth Assistant
## M6 — Error Troubleshooter
## M7 — API Doc Analyzer
## M8 — Field Mapping & Workflow Designer
## M9 — Handover Document Generator
