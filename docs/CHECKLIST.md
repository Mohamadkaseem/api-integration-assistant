# Project Checklist

**Current state:** Milestone 3 built and tested with a mock Claude. Waiting for you to add your API key and test with real Claude.

## M1 — Foundations ✅
- [x] Folders: `backend/`, `frontend/`, `docs/`
- [x] `.gitignore` excludes secrets and the local database
- [x] FastAPI backend, settings from `.env`
- [x] `GET /api/health` + 2 passing tests
- [x] Next.js + TypeScript + Tailwind UI with sidebar for all 9 features
- [x] Dashboard with live backend status
- [x] Research report (`docs/RESEARCH.md`) and plan (`docs/PLAN.md`)
- [x] Run locally on Windows: tests pass, green "Connected" dot

## M2 — Projects & SQLite ✅
- [x] SQLModel + SQLite database file (`backend/data/app.db`, not committed to Git)
- [x] Project model (name, source/target app, requirement, status, notes, timestamps)
- [x] API: list / create / view / edit / delete (`/api/projects`)
- [x] Projects A, B, C pre-loaded on first start (never overwrites your edits)
- [x] Tests use a throw-away in-memory database — 10 passing
- [x] Projects page, "New project" form, detail page with Edit and Delete (delete asks first)
- [x] Dashboard "Integration projects" count is real
- [x] Fixed test warning (httpx → httpx2)
- [x] Verified on Windows: create / edit / delete / data survives restart

## M3 — AI + Requirement Analyzer ✅ (built & tested with mock Claude)
- [x] Official Anthropic SDK (`anthropic` 2.10), model `claude-opus-5-5`, effort `high` (configurable in `.env`)
- [x] Provider abstraction (`app/ai/provider.py`) so another AI can be added later
- [x] API key read from `backend/.env` only (never sent to the browser, hidden in logs)
- [x] Structured output: Claude must return the exact `RequirementAnalysis` schema
- [x] Rules: no invented endpoints, assumptions listed separately, prioritized clarification questions
- [x] Automatic fallback model if Claude declines a request
- [x] Clear error messages: no key, wrong key, no credit, rate limit, network, declined
- [x] Analyses saved per project with history; re-analyze with client answers
- [x] Requirement Analyzer page + "Analyze requirement" button on each project
- [x] 24 backend tests (fake AI + mock Claude server), browser flow tested
- [ ] **You:** add API key, analyze Projects A and B with real Claude
## M4 — Request Builder & API testing
## M5 — Credentials & Auth Assistant
## M6 — Error Troubleshooter
## M7 — API Doc Analyzer
## M8 — Field Mapping & Workflow Designer
## M9 — Handover Document Generator
