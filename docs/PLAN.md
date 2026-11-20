# My API Integration Assistant — Plan

## Purpose
A **personal, local** tool that turns a client's integration requirement into a working, tested, documented API integration. It covers the 13 steps of my daily workflow:

**requirement → docs → endpoints → auth → data → mapping → triggers → sequence → testing → troubleshooting → handover.**

Not a SaaS: single user, runs on my computer, no billing, no multi-tenant features.

Rules the AI follows:
- **Never invent endpoints.** Every endpoint is either *verified* (found in docs I gave it) or clearly labelled *assumption*.
- **Ask clarification questions** when a requirement is unclear.
- **Show every API call before running it.** Writes and deletes (POST/PUT/PATCH/DELETE) need my confirmation.
- **Never put credentials** in the browser, in logs, or in AI prompts.

## Architecture (simplest that works)
```
Browser (localhost:3000)          FastAPI backend (localhost:8000)            Outside world
Next.js UI — no secrets   ──►     api/routes/   REST endpoints
                                  services/     logic
                                  ai/           Claude client + prompts       ──► Claude API
                                  parsers/      OpenAPI / Postman / PDF
                                  http_runner/  executes test API calls       ──► Zoho, HubSpot, Zwayam…
                                  security/     URL checks, encryption
                                  db.py         SQLite file (data/app.db)
```
- **One backend, one database file.** No Docker, queues, microservices or agent frameworks.
- **AI layer:**
  - A tiny `AIProvider` interface; `ClaudeProvider` is the first implementation.
  - Agents are plain Python functions that ask for **structured JSON** and validate it with Pydantic.
- **API execution:** `httpx` (Python HTTP client).
- **Safety checks before every call:**
  - The URL must be http(s).
  - It must not be a private or internal network address.
  - It must be on my allowed-hosts list.
  - Write methods need my confirmation.
- **Credentials:** encrypted in SQLite with a key kept in `.env`, and decrypted only at the moment a request is sent.
- **Workflow view:** a Mermaid diagram generated from the workflow steps.
- **Approval/retry:** a simple status field plus a retry loop (the LangGraph ideas, without LangGraph).

## Dependencies and why
| Dependency | Why |
|---|---|
| FastAPI + Uvicorn | Backend web framework and server |
| pydantic-settings | Settings from `.env` |
| SQLModel (SQLAlchemy + Pydantic, by FastAPI's author) | SQLite database with beginner-friendly models |
| anthropic | Claude API |
| httpx | Execute test API calls |
| cryptography | Encrypt stored credentials |
| PyYAML | Read OpenAPI YAML |
| pypdf | Extract text from PDF docs |
| python-multipart | File uploads |
| Next.js + TypeScript + Tailwind | UI |
| mermaid (npm) | Workflow diagrams |

Each one is added only in the milestone that needs it.

## MVP scope — the minimum useful version
1. Integration **projects** saved in SQLite (A: Zwayam↔Zoho Sign, B: HubSpot→Zoho CRM, C: Zoho Sign testing).
2. **Requirement Analyzer:**
   - Extracts trigger, source, target, data, conditions, actions and outcome.
   - Asks clarification questions.
3. **Request Builder + API testing:**
   - Choose method, URL, headers, query params, body and auth.
   - See status, headers, body and timing.
   - Writes need confirmation.
4. **Credentials + Auth assistant:**
   - API key, Bearer, Basic and OAuth 2.0 with refresh token (Zoho first).
   - Stored encrypted.
5. **Error Troubleshooter:**
   - Explains the error, the likely cause and the field at fault.
   - Produces a corrected request, ready to re-test.
6. **API Doc Analyzer:**
   - OpenAPI JSON/YAML and Postman collections (verified).
   - Text, PDF and URL (AI-extracted, marked unverified).
7. **Field Mapping + Workflow Designer:**
   - Editable mapping table, with type, date and picklist warnings.
   - Mermaid workflow diagram.
8. **Handover Document Generator:** Markdown and Word (.docx) export.

**Postponed:**
- An engine that runs integrations automatically (webhooks, schedules).
- A drag-and-drop editor.
- Code generation.
- An autonomous agent.
- Running the app online.

## Roadmap
| # | Milestone | Delivers | Complexity |
|---|---|---|---|
| **M1** | Foundations ✅ | Backend + UI shell + health check + tests | Low |
| **M2** | Projects & SQLite ✅ | Save/list/edit integration projects; A, B, C pre-loaded | Low |
| **M3** | AI + Requirement Analyzer ✅ | Claude connected; structured analysis + clarification questions | Medium |
| **M4** | API Doc Analyzer ✅ | Upload (OpenAPI/Postman/PDF/text) and URL import; verified / quoted / unverified endpoints | Medium–High |
| **M5** | Request Builder & API testing ✅ | Postman-like screen, safe execution, write confirmation, request history; start from an imported endpoint | Medium |
| **M6** | Credentials & OAuth ✅ | Encrypted credentials, API key/Bearer/Basic, Zoho OAuth + auto refresh (Project C) | Medium–High |
| M7 | Error Troubleshooter | Paste or auto-capture errors → explanation + corrected request → re-test | Low–Medium |
| M8 | Endpoint matching, Field Mapping & Workflow | Pick endpoints for a requirement from imported docs, editable mappings, Mermaid diagram | Medium |
| M9 | Handover Document Generator | Full developer handover doc, Markdown + .docx export | Low–Medium |
| Later | Simple execution engine | Run saved workflows: webhooks/polling, retries, logs, approval pauses | High |

**Order change (2026-11-19):** the API Doc Analyzer moved up to M4 at your request, because real documentation is the
foundation for everything after it (requests, mappings, workflows).

**Complexity scale:** Low = 1–2 sittings, Medium = 3–5, High = 6+.

## Main risks
| Risk | Mitigation |
|---|---|
| AI invents endpoints or fields | Catalogue from parsed docs; AI must cite catalogue IDs; backend rejects unknown IDs |
| Instructions hidden inside uploaded docs | Docs are passed as quoted data; the AI has no tools that act on its own; outputs are schema-validated |
| Accidentally modifying real client data | Confirmation for writes; "sandbox" label on credentials; allowed-hosts list |
| Token leakage | Encrypted at rest; masked in UI; redacted from logs and AI prompts |
| Huge API docs (Zoho, HubSpot) | Parse deterministically, then send the AI only the relevant endpoints |
| Zwayam has limited public docs | Use what the client provides; mark gaps as "needs confirmation from vendor" |
| Claude API cost | Small prompts; cache results per project; it's pay-per-use (typically cents per analysis) |
