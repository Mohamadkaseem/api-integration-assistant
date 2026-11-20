# Project Checklist

**Current state:** M4 verified on Windows (spec import, upload fixes). Claude key connects; live AI test of M3/M4 postponed until credit is added. M5 built and tested here; waiting for you to test on Windows.

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
- [x] API key loaded and accepted by Anthropic on Windows
- [ ] **Later (needs credit):** analyze Projects A and B with real Claude
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
- [x] Verified on Windows: 59 tests pass, upload form fixes
- [ ] **Later (needs credit):** PDF / pasted-text import with real Claude

## M5 — Request Builder & API testing ✅ (built & tested here)
- [x] GET / POST / PUT / PATCH / DELETE / HEAD / OPTIONS with query params, headers, JSON / text / form body
- [x] Auth: Bearer (custom prefix, e.g. Zoho-oauthtoken), Basic, API key in header or query
- [x] Start from an imported endpoint (URL, params, example body built from the schema; Postman {{variables}} filled)
- [x] "Try in Request Builder" button on every endpoint in the API Doc Analyzer
- [x] Write methods require confirmation (in the UI and enforced by the backend)
- [x] Private / local addresses blocked (opt-in: ALLOW_PRIVATE_NETWORK_REQUESTS=true); redirects shown, not followed
- [x] 30 s timeout, 5 MB response limit, binary responses not dumped, invalid JSON caught before sending
- [x] Warning for unfilled placeholders like {id} or {{base_url}}
- [x] History: reopen / resend / delete; secrets never stored (headers, query, auth, and tokens inside saved bodies masked)
- [x] Copy as cURL with secrets replaced by placeholders
- [x] Dashboard shows real counts (sent / successful / failed)
- [x] 74 backend tests; browser flow tested incl. a real internet request
- [ ] **You:** send a real GET to an API you use (e.g. Zoho with an access token from the Zoho API console)
## M6 — Credentials & Auth Assistant
## M7 — Error Troubleshooter
## M8 — Endpoint matching, Field Mapping & Workflow Designer
## M9 — Handover Document Generator
