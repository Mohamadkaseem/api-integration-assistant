# Project Checklist

**Current state:** M3 and M4 built and tested here (with a mock Claude). Waiting for you to test both on your computer with your API key.

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
## M4 — API Doc Analyzer ✅ (built & tested here)
- [x] Upload: OpenAPI 3 / Swagger 2 (JSON or YAML) and Postman v2 collections, read by code (no AI) → "Verified · from spec"
- [x] Upload: PDF (text-based) and pasted text, read by Claude in parts → every endpoint quote-checked
- [x] Endpoints whose quote/path is not found word-for-word are marked "Unverified" (never silently trusted)
- [x] Import from URL with SSRF protection (no localhost / private networks / metadata IPs, redirects checked, 30 MB / 20 s limits)
- [x] Postman header and auth values (possible secrets) are never stored
- [x] Clear messages for scanned PDFs, JavaScript-only pages, too-long documents, missing API key
- [x] Documentation page: base URLs, auth schemes, search / method / trust filters, endpoint details, remove endpoint
- [x] Tested with real public specs (GitHub REST API: 1,281 endpoints in ~4 s)
- [x] 59 backend tests; browser flow tested
- [ ] **You:** import real docs for your projects (e.g. Zoho Sign, Zoho CRM, a Zwayam PDF)

## M5 — Request Builder & API testing
## M6 — Credentials & Auth Assistant
## M7 — Error Troubleshooter
## M8 — Endpoint matching, Field Mapping & Workflow Designer
## M9 — Handover Document Generator
