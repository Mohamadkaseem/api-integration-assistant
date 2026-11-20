# Project Checklist

**Current state:** M4 verified on Windows (spec import, upload fixes). Claude key connects; live AI test of M3/M4 postponed until credit is added. All 9 milestones complete and verified on Windows. Remaining: live test of the AI features once Claude credit is added.

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

## M5 — Request Builder & API testing ✅
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
- [x] Verified on Windows: real GET to api.github.com → 200 OK
- [ ] Optional: real Zoho call with an access token
## M6 — Credentials & OAuth ✅
- [x] Saved credentials: API key, Bearer token, Basic auth, OAuth 2.0 — secrets encrypted (Fernet) in SQLite
- [x] Encryption key auto-created in backend/data/credentials.key (git-ignored; back it up) or CREDENTIALS_KEY in .env
- [x] Secrets never returned to the browser (only a hint like "…a1b2"); edits keep secrets when fields are left blank
- [x] Zoho OAuth for all data centres (com, in, eu, com.au, jp, ca); Self Client code exchange
- [x] Browser sign-in (authorization code flow) with one-time state; Zoho "accounts-server" data-centre switch
- [x] Generic OAuth 2.0 providers (HubSpot, Google, ...): token URL, client secret in body or Basic header
- [x] Access token renewed automatically before expiry, and once more after a 401
- [x] Plain-language OAuth errors (invalid_code, invalid_client, redirect mismatch, invalid_grant, ...), incl. Zoho's errors sent with HTTP 200
- [x] Request Builder: "Saved credential" in the Auth tab; production credentials flagged in the write confirmation
- [x] 85 backend tests; browser flow tested (connect, test connection, use in requests, nothing secret in history or DB)
- [x] Real Zoho CRM account (zoho.in) connected via Self Client; token refresh works
- [x] Real Zoho CRM API call (GET Accounts) with the saved credential → 200, 3 records
## M7 — Error Troubleshooter ✅
- [x] Built-in explanations (no AI, free): HTTP status codes, Zoho codes (INVALID_DATA, MANDATORY_NOT_FOUND, DUPLICATE_DATA, INVALID_TOKEN, OAUTH_SCOPE_MISMATCH, ...), HubSpot categories, OAuth errors, network problems
- [x] Finds the field at fault (Zoho details.api_name, HubSpot context.propertyName, quoted names in messages) and the expected data type
- [x] Retry-After and "retrying may work" hints for rate limits and server errors
- [x] "Troubleshoot this error" under every failed response in the Request Builder
- [x] Error Troubleshooter page: paste any error, or pick a failed request from history
- [x] "Explain with AI": Claude gets the REDACTED request + response + built-in diagnosis + imported endpoint docs
- [x] AI returns cause, field at fault, fix steps, confidence, and a corrected request → "Open in Request Builder"
- [x] 101 backend tests (incl. secrets never reaching the AI); browser flow tested end to end
- [x] Verified on Windows: pasted Zoho error explained (after fixing the empty-status-code bug)
- [ ] **Later (needs credit):** "Explain with AI" with a real error
## M8 — Integration Design: endpoints, field mapping, workflow ✅
- [x] One design per project: trigger, documentation to use, steps, field mappings
- [x] Steps from the latest requirement analysis, or added/edited/reordered manually (free)
- [x] Choose each step's endpoint from imported docs; backend refuses endpoints outside the selected docs
- [x] "Match endpoints with AI": Claude sees only a candidate list; invented IDs are rejected; manual choices kept
- [x] Big specs pre-filtered to the 400 most relevant endpoints
- [x] "Documentation still needed" list (e.g. missing HubSpot or Zwayam endpoints)
- [x] Editable field mapping table (transform, required, issue type: type/date/picklist/nested)
- [x] "Suggest mappings with AI": every field checked against the docs → documented / assumed; your rows kept
- [x] Workflow diagram (Mermaid) generated from the steps: decisions, waits, missing endpoints highlighted; Mermaid source to copy
- [x] 112 backend tests; browser flow tested with a fake Claude
- [x] Verified on Windows: Project A steps added manually, workflow diagram with "waits for" labels
- [ ] **Later (needs credit):** AI matching and mapping with real docs
## M9 — Developer Handover Document ✅
- [x] One document per project, assembled without AI: overview, trigger & workflow, endpoints, authentication, mappings, error handling, test cases, sample requests, assumptions & open points
- [x] Endpoint sections with full URL (Postman {{variables}} filled), parameters, request body, responses, trust level
- [x] Authentication described from docs and saved credentials — never secrets
- [x] Test cases generated from the workflow (happy path, every branch, every wait, invalid data, duplicates, token expiry, outage)
- [x] Open points collected: missing docs, steps without endpoints, assumed mappings, unverified endpoints, open questions
- [x] Preview page; Word (.docx) export with the workflow diagram as a picture; Markdown export (Mermaid diagram) and copy
- [x] Optional "Improve with AI": executive summary + extra edge-case test cases
- [x] 119 backend tests (incl. no secrets in Word/Markdown/AI input); browser flow tested, picture verified inside the .docx
- [x] Verified on Windows: handover document generated and exported
