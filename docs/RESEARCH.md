# Open-Source Research Report

Researched 2026-11-19 by reading only the relevant folders of each repository (shallow, sparse clones).
Because this is a **personal tool**, licenses matter less than for a product you sell — but all six are permissive anyway.

**Legend:**
- **Reference** = we read it to learn a pattern and write our own code.
- **Dependency** = we install it.

## Summary
| Repository | License | Verdict for us | Needed for MVP? |
|---|---|---|---|
| Activepieces | MIT (except `packages/ee/`, commercial) | **Reference** — best model for connectors, auth, triggers | No (reference only) |
| LangGraph | MIT | **Reference** — borrow the "pause for approval" idea; do not install | No |
| FastAPI | MIT | **Dependency** — already our backend | **Yes** (in use since M1) |
| swagger-parser | Apache-2.0 | **Reference** — it is Java, we use Python; copy its *safe URL resolver* idea | No |
| Langflow | MIT | **Design reference** for the workflow view | No |
| postman-collection | Apache-2.0 | **Reference** — it is Node.js; we read/write the Collection v2.1 JSON format ourselves | No (import/export later) |

---

## 1. Activepieces — https://github.com/activepieces/activepieces
**What it does:** an open-source automation tool (like Zapier). Each app integration is called a **"piece"**.

**Relevant architecture:**
```
packages/pieces/framework/src/lib/      ← the "rules" every connector follows
   piece.ts           createPiece(): name, auth, actions[], triggers[]
   action/action.ts   createAction(): name, props (inputs), run()
   trigger/trigger.ts createTrigger(): POLLING or WEBHOOK strategy
   property/          input types (text, dropdown, json, file, …)
   property/authentication/  SecretText (API key), BasicAuth, CustomAuth, OAuth2
packages/pieces/core/http/               ← generic "Send HTTP request" action
packages/pieces/community/zoho-crm/src/  ← a real connector worth reading
   lib/auth.ts         OAuth2 with a data-centre dropdown (zoho.com / .eu / .in / .com.au / .jp / zohocloud.ca)
   lib/actions/upsert-record.ts   create-or-update using duplicate-check fields (= our Project B!)
   lib/common/polling.ts          "new record" trigger by polling with a time cursor
   lib/common/host-guard.ts       only sends the Zoho token to Zoho API hosts
packages/pieces/community/hubspot/src/   ← HubSpot connector (create-company, find-company, triggers)
```
A connector in Activepieces is basically:

> **auth** + a list of **actions** (each with typed inputs and a `run()` that makes an HTTP call) + a list of **triggers** (polling or webhook).

**What to learn / reuse (as patterns, in our own Python):**
- **One standard shape for describing an API action.** Each action has a name, an input schema, an output schema, and a flag saying whether it is "read" or "write". We'll use the same shape in our endpoint catalogue. Activepieces marks actions `classification: 'WRITE'`; we'll use that flag to ask for your approval.
- **Zoho OAuth details:**
  - The data-centre handling: `accounts.{location}/oauth/v2/token`.
  - The token host guard: never send a token to a host other than the one it was issued for.
- **Real-world knowledge for Project B:**
  - Zoho's upsert duplicate-check fields (`Account_Name` for Accounts).
  - The warning that upsert without a duplicate-check value creates duplicates.
- **Trigger strategies:** *polling* (ask every N minutes "anything new?") vs *webhook* (the app calls us). Both apply to Zwayam/Zoho Sign.

**What NOT to take:** the whole engine (TypeScript, Redis, workers, Docker). Far too heavy for a personal tool. There is **no Zoho Sign piece**, so Project A relies on Zoho Sign's own docs.

## 2. LangGraph — https://github.com/langchain-ai/langgraph
**What it does:** a Python library for building AI agents as a graph of steps, with saved state.

**Relevant files:**
- `libs/langgraph/langgraph/types.py`:
  - `interrupt()` pauses the graph and waits for a human.
  - `Command(resume=…)` continues it.
  - `RetryPolicy` sets retries with backoff (0.5s, ×2, max 3 attempts).
- `libs/checkpoint-sqlite/` saves state to SQLite so a paused run can resume later.

**What to learn:**
1. **State:** keep one record of "where we are" for each run.
2. **Steps:** small functions that read and update that state.
3. **Approval:** pause before risky steps and resume after you say yes.
4. **Retry policy:** retry failed steps with growing waits between attempts.

**Verdict:** we implement these ideas in ~100 lines of plain Python:
- a `status` column with values `running`, `waiting_for_approval`, `done` or `failed`,
- a list of steps,
- a retry loop.

Installing LangGraph would add LangChain concepts you'd have to learn without real benefit at this size. **Revisit only in the late "autonomous agent" stage.**

## 3. FastAPI — https://github.com/fastapi/fastapi
**What it does:** the Python web framework our backend already uses. Learn from the docs (https://fastapi.tiangolo.com), not the source.

**Features we use and when:**
| Concept | Docs page | Our milestone |
|---|---|---|
| Path operations / routers | "Bigger Applications" | M1 ✅ |
| Pydantic request/response models | "Request Body", "Response Model" | M2 |
| Validation errors (422) | "Handling Errors" | M2 |
| File uploads (`UploadFile`, needs `python-multipart`) | "Request Files" | M7 |
| Interactive docs at `/docs` | "First Steps" | M1 ✅ |
| Dependencies (DB session) | "Dependencies" | M2 |

## 4. swagger-parser — https://github.com/swagger-api/swagger-parser
**What it does:** a **Java** library that reads Swagger 2.0 / OpenAPI 3 files, resolves `$ref` links, and converts v2 to v3.

**Relevant modules:**
- `modules/swagger-parser-v3`: the main parser.
- `modules/swagger-parser-v2-converter`: converts Swagger 2.0 files to OpenAPI 3.
- `modules/swagger-parser-safe-url-resolver`: refuses to fetch `$ref` URLs that point to private or internal network addresses. This is an SSRF guard, and **we copy this idea**.

**Verdict: don't use it (Java).** Python options:
- **PyYAML** (reads YAML) plus our own small extractor that walks `paths → methods → parameters/requestBody/responses/security`. Simplest, and fully understandable.
- **prance** (MIT) only if we hit complex multi-file `$ref`s. It resolves references and supports both Swagger 2.0 and OpenAPI 3.

We start with PyYAML plus our own extractor, and resolve only local `#/components/...` refs ourselves.

## 5. Langflow — https://github.com/langflow-ai/langflow
**What it does:** a visual drag-and-drop builder for AI flows. The frontend (`src/frontend/src`) uses **React Flow (`@xyflow/react`, MIT)** for nodes and connections. The backend (`src/lfx`) holds the components.

**What to learn:** the visual vocabulary:
- **nodes**: a component with inputs and outputs,
- **edges**: connections between nodes,
- **handles**: the typed ports where edges attach.

**Verdict:** design reference only. For our workflow view we start with **Mermaid**: the AI writes a short text diagram and it renders as a flowchart. That's far simpler than a drag-and-drop editor. Upgrade to `@xyflow/react` later only if you want to drag boxes around.

## 6. postman-collection — https://github.com/postmanlabs/postman-collection
**What it does:** a Node.js SDK for the **Postman Collection v2.1** format. `lib/collection/` contains:
- `request.js`, `url.js`, `header.js`, `request-auth.js`, `request-body.js` for the request itself,
- `variable.js` for `{{variables}}`,
- `item-group.js` for folders.

**Verdict:** we don't need the SDK (it's JavaScript). What's valuable is the **file format**:
- Many API vendors, including Zoho, publish Postman collections.
- So **importing a Postman collection** gives us verified endpoints and sample requests for free.
- **Exporting** our requests as a collection lets a developer open them in Postman.

The format is plain JSON (`info`, `item[]`, `request{method,url,header,body,auth}`, `variable[]`), so Python reads it directly. Planned for M7.
