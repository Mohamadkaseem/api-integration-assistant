"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { KeyValueEditor } from "@/components/KeyValueEditor";
import { ResponseViewer } from "@/components/ResponseViewer";
import {
  deleteHistory,
  getDoc,
  getHistory,
  listCredentials,
  listDocs,
  listHistory,
  listProjects,
  sendRequest,
  type ApiDocDetail,
  type ApiDocSummary,
  type Credential,
  type HistoryDetail,
  type HistoryItem,
  type OutgoingRequest,
  type Project,
  type RunResult,
} from "@/lib/api";
import { METHOD_STYLE } from "@/lib/docs";
import { EMPTY_AUTH, EMPTY_REQUEST, MASK, WRITE_METHODS, findPlaceholders, requestFromEndpoint, toCurl } from "@/lib/requests";

type Tab = "params" | "headers" | "body" | "auth";
const METHODS: OutgoingRequest["method"][] = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];
const input = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";

export function RequestBuilder() {
  const searchParams = useSearchParams();
  const [req, setReq] = useState<OutgoingRequest>(EMPTY_REQUEST);
  const [tab, setTab] = useState<Tab>("params");
  const [result, setResult] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [endpointId, setEndpointId] = useState<number | null>(null);
  const [docs, setDocs] = useState<ApiDocSummary[]>([]);
  const [pickerDoc, setPickerDoc] = useState<ApiDocDetail | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [copied, setCopied] = useState(false);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [credentialId, setCredentialId] = useState("");

  const refreshHistory = useCallback(() => {
    listHistory().then(setHistory).catch(() => setHistory([]));
  }, []);

  function loadEndpoint(doc: ApiDocDetail, id: number) {
    const endpoint = doc.endpoints.find((e) => e.id === id);
    if (!endpoint) return;
    setReq(requestFromEndpoint(doc, endpoint));
    setEndpointId(endpoint.id);
    if (doc.project_id) setProjectId(String(doc.project_id));
    setResult(null);
    const auth = doc.auth_schemes.map((a) => `${a.name} (${a.type})`).join(", ");
    setNotice(
      `Loaded ${endpoint.method} ${endpoint.path} from ${doc.app_name}.` +
        (auth ? ` This API uses: ${auth} — set it up in the Auth tab.` : "") +
        (endpoint.verification === "unverified" ? " ⚠ This endpoint is UNVERIFIED — check the original documentation first." : ""),
    );
  }

  function applyHistoryItem(item: HistoryDetail) {
    {
      const saved = item.request;
      const hadSecrets = JSON.stringify(saved).includes(MASK) || ((saved.auth?.type ?? "none") !== "none" && !saved.credential_id);
      setReq({
        ...EMPTY_REQUEST,
        ...saved,
        url: (saved.url ?? "").replaceAll(encodeURIComponent(MASK), ""),
        params: saved.params ?? [],
        headers: saved.headers ?? [],
        form: saved.form ?? [],
        auth: { ...EMPTY_AUTH, ...saved.auth },
      } as OutgoingRequest);
      setEndpointId(item.endpoint_id);
      setProjectId(item.project_id ? String(item.project_id) : "");
      setCredentialId(saved.credential_id ? String(saved.credential_id) : "");
      setResult(null);
      setNotice(hadSecrets ? "Reopened from history. Secret values (tokens, passwords, keys) are never saved — enter them again before sending." : "Reopened from history.");
    }
  }

  function loadHistoryItem(id: number) {
    getHistory(id)
      .then(applyHistoryItem)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]));
    listDocs().then(setDocs).catch(() => setDocs([]));
    listCredentials().then(setCredentials).catch(() => setCredentials([]));
    refreshHistory();
    // Opened from an imported endpoint (?doc=1&endpoint=5) or from history (?history=3)
    const docParam = searchParams.get("doc");
    const endpointParam = searchParams.get("endpoint");
    const historyParam = searchParams.get("history");
    if (docParam && endpointParam) {
      getDoc(Number(docParam))
        .then((doc) => {
          setPickerDoc(doc);
          loadEndpoint(doc, Number(endpointParam));
        })
        .catch((err: Error) => setError(err.message));
    } else if (historyParam) {
      getHistory(Number(historyParam))
        .then(applyHistoryItem)
        .catch((err: Error) => setError(err.message));
    }
    // Runs once when the page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const placeholders = findPlaceholders(req.url);
  const isWrite = WRITE_METHODS.includes(req.method);

  async function send() {
    setError(null);
    if (!req.url.trim()) return setError("Enter a URL.");
    if (placeholders.length && !window.confirm(`The URL still contains placeholders: ${placeholders.join(", ")}.\n\nSend anyway?`)) return;
    if (isWrite) {
      let host = req.url;
      try {
        host = new URL(req.url).host;
      } catch {
        /* keep raw */
      }
      const cred = credentials.find((x) => String(x.id) === credentialId);
      const production = cred?.environment === "production" ? `\n\n⚠ Using PRODUCTION credential "${cred.name}".` : "";
      const ok = window.confirm(
        `Send ${req.method} to ${host}?\n\n${req.method} requests can CREATE, CHANGE or DELETE real data.\nUse a sandbox / test account when possible.${production}`,
      );
      if (!ok) return;
    }
    setBusy(true);
    try {
      const response = await sendRequest({
        request: req,
        confirm_write: isWrite,
        project_id: projectId ? Number(projectId) : null,
        endpoint_id: endpointId,
        credential_id: credentialId ? Number(credentialId) : null,
      });
      setResult(response);
      refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function copyCurl() {
    await navigator.clipboard.writeText(toCurl(req));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const set = (patch: Partial<OutgoingRequest>) => setReq((r) => ({ ...r, ...patch }));
  const setAuth = (patch: Partial<OutgoingRequest["auth"]>) => setReq((r) => ({ ...r, auth: { ...r.auth, ...patch } }));
  const count = (rows: { enabled: boolean; name: string }[]) => rows.filter((r) => r.enabled && r.name).length;

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_18rem]">
      <div className="min-w-0 space-y-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Request Builder</h1>
          <p className="mt-1 text-slate-600">Build and send API requests. Start from an imported endpoint or type your own.</p>
        </div>

        {/* Start from imported documentation */}
        <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-600">
            Start from imported documentation
            <select
              className={`${input} mt-1`}
              value={pickerDoc?.id ?? ""}
              onChange={(e) => {
                const id = Number(e.target.value);
                if (!id) return setPickerDoc(null);
                getDoc(id).then(setPickerDoc).catch((err: Error) => setError(err.message));
              }}
            >
              <option value="">Choose documentation…</option>
              {docs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.app_name} — {d.title || d.source_ref} ({d.endpoint_count})
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-medium text-slate-600">
            Endpoint
            <select
              className={`${input} mt-1`}
              disabled={!pickerDoc}
              value={endpointId && pickerDoc?.endpoints.some((e) => e.id === endpointId) ? endpointId : ""}
              onChange={(e) => pickerDoc && loadEndpoint(pickerDoc, Number(e.target.value))}
            >
              <option value="">{pickerDoc ? "Choose endpoint…" : "Choose documentation first"}</option>
              {pickerDoc?.endpoints.slice(0, 2000).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.method} {e.path} {e.summary ? `— ${e.summary.slice(0, 60)}` : ""}
                </option>
              ))}
            </select>
          </label>
        </div>

        {notice && <p className="rounded-md bg-sky-50 px-3 py-2 text-sm text-sky-900">{notice}</p>}

        {/* Method + URL + Send */}
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={req.method}
            onChange={(e) => set({ method: e.target.value as OutgoingRequest["method"] })}
            className={`rounded-md px-3 py-2 text-sm font-bold text-white ${METHOD_STYLE[req.method] ?? "bg-slate-600"}`}
          >
            {METHODS.map((m) => (
              <option key={m} value={m} className="bg-white text-slate-900">
                {m}
              </option>
            ))}
          </select>
          <input className={`${input} font-mono`} value={req.url} onChange={(e) => set({ url: e.target.value })} placeholder="https://api.example.com/v1/resource" />
          <button onClick={send} disabled={busy} className="rounded-md bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            {busy ? "Sending…" : "Send"}
          </button>
        </div>
        {placeholders.length > 0 && (
          <p className="text-xs text-amber-800">Replace the placeholders before sending: {placeholders.join(", ")}</p>
        )}
        {isWrite && <p className="text-xs text-rose-700">{req.method} can create, change or delete real data — you will be asked to confirm.</p>}

        {/* Tabs */}
        <div className="rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap gap-1 border-b border-slate-100 px-3 pt-2 text-sm">
            {(
              [
                ["params", `Params (${count(req.params)})`],
                ["headers", `Headers (${count(req.headers)})`],
                ["body", `Body${req.body_type !== "none" ? ` (${req.body_type})` : ""}`],
                ["auth", `Auth${credentialId ? " (saved)" : req.auth.type !== "none" ? ` (${req.auth.type})` : ""}`],
              ] as [Tab, string][]
            ).map(([value, label]) => (
              <button key={value} onClick={() => setTab(value)} className={`-mb-px border-b-2 px-3 py-2 ${tab === value ? "border-indigo-600 font-medium text-slate-900" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
                {label}
              </button>
            ))}
          </div>
          <div className="p-4">
            {tab === "params" && <KeyValueEditor rows={req.params} onChange={(params) => set({ params })} namePlaceholder="parameter" />}
            {tab === "headers" && <KeyValueEditor rows={req.headers} onChange={(headers) => set({ headers })} namePlaceholder="Header-Name" />}
            {tab === "body" && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-4 text-sm">
                  {(["none", "json", "text", "form"] as const).map((t) => (
                    <label key={t} className="flex items-center gap-1.5">
                      <input type="radio" checked={req.body_type === t} onChange={() => set({ body_type: t })} />
                      {t === "none" ? "No body" : t === "json" ? "JSON" : t === "text" ? "Text" : "Form (urlencoded)"}
                    </label>
                  ))}
                </div>
                {(req.body_type === "json" || req.body_type === "text") && (
                  <textarea className={`${input} min-h-56 font-mono text-xs`} value={req.body} onChange={(e) => set({ body: e.target.value })} placeholder={req.body_type === "json" ? '{\n  "key": "value"\n}' : ""} />
                )}
                {req.body_type === "form" && <KeyValueEditor rows={req.form} onChange={(form) => set({ form })} namePlaceholder="field" />}
                {["GET", "HEAD"].includes(req.method) && req.body_type !== "none" && <p className="text-xs text-amber-800">{req.method} requests are sent without a body.</p>}
              </div>
            )}
            {tab === "auth" && (
              <div className="space-y-3 text-sm">
                <label className="block text-xs font-medium text-slate-600">
                  Saved credential (recommended)
                  <select className={`${input} mt-1`} value={credentialId} onChange={(e) => setCredentialId(e.target.value)}>
                    <option value="">None — type auth details below</option>
                    {credentials.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.environment}){c.status !== "ready" ? " — not ready" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                {credentialId && (() => {
                  const c = credentials.find((x) => String(x.id) === credentialId);
                  return (
                    <p className={`rounded-md px-3 py-2 text-xs ${c?.environment === "production" ? "bg-rose-50 text-rose-800" : "bg-slate-50 text-slate-600"}`}>
                      Using “{c?.name}”{c?.type === "oauth2" ? " — the access token is renewed automatically when needed." : "."}
                      {c?.environment === "production" ? " ⚠ PRODUCTION credential: requests affect real data." : ""}
                    </p>
                  );
                })()}
                {!credentialId && <>
                <select className={input} value={req.auth.type} onChange={(e) => setAuth({ type: e.target.value as OutgoingRequest["auth"]["type"] })}>
                  <option value="none">No auth</option>
                  <option value="bearer">Bearer / OAuth access token</option>
                  <option value="basic">Basic auth (username + password)</option>
                  <option value="api_key">API key</option>
                </select>
                {req.auth.type === "bearer" && (
                  <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
                    <label className="text-xs text-slate-600">
                      Prefix
                      <input className={`${input} mt-1`} value={req.auth.token_prefix} onChange={(e) => setAuth({ token_prefix: e.target.value })} />
                      <span className="mt-1 block text-slate-500">Zoho uses &quot;Zoho-oauthtoken&quot;</span>
                    </label>
                    <label className="text-xs text-slate-600">
                      Token
                      <input className={`${input} mt-1 font-mono`} type="password" value={req.auth.token} onChange={(e) => setAuth({ token: e.target.value })} autoComplete="off" />
                    </label>
                  </div>
                )}
                {req.auth.type === "basic" && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input className={input} placeholder="Username" value={req.auth.username} onChange={(e) => setAuth({ username: e.target.value })} autoComplete="off" />
                    <input className={input} placeholder="Password" type="password" value={req.auth.password} onChange={(e) => setAuth({ password: e.target.value })} autoComplete="off" />
                  </div>
                )}
                {req.auth.type === "api_key" && (
                  <div className="grid gap-3 sm:grid-cols-3">
                    <input className={input} placeholder="Name, e.g. X-API-Key" value={req.auth.key_name} onChange={(e) => setAuth({ key_name: e.target.value })} />
                    <input className={`${input} font-mono`} placeholder="Value" type="password" value={req.auth.key_value} onChange={(e) => setAuth({ key_value: e.target.value })} autoComplete="off" />
                    <select className={input} value={req.auth.key_in} onChange={(e) => setAuth({ key_in: e.target.value as "header" | "query" })}>
                      <option value="header">Send in header</option>
                      <option value="query">Send in URL query</option>
                    </select>
                  </div>
                )}
                <p className="text-xs text-slate-500">
                  Typed secrets are used only for this request and never saved (history shows ••••••). To reuse a secret, save it under Credentials.
                </p>
                </>}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2 text-slate-600">
            Save to project
            <select className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">—</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <button onClick={copyCurl} disabled={!req.url} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            {copied ? "Copied ✓" : "Copy as cURL"}
          </button>
          <button
            onClick={() => {
              setReq(EMPTY_REQUEST);
              setResult(null);
              setNotice(null);
              setEndpointId(null);
              setCredentialId("");
            }}
            className="text-slate-500 hover:text-slate-800"
          >
            Clear
          </button>
        </div>

        {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {result && <ResponseViewer result={result} />}
      </div>

      {/* History */}
      <aside className="space-y-2">
        <h2 className="text-sm font-semibold text-slate-900">History</h2>
        {history.length === 0 && <p className="text-xs text-slate-500">Requests you send appear here.</p>}
        <ul className="space-y-1.5">
          {history.map((h) => (
            <li key={h.id} className="group flex items-start gap-2 rounded-md border border-slate-200 bg-white p-2 text-xs">
              <button onClick={() => loadHistoryItem(h.id)} className="min-w-0 flex-1 text-left">
                <span className="flex items-center gap-1.5">
                  <span className="font-bold text-slate-700">{h.method}</span>
                  <span className={h.status_code === null ? "text-rose-700" : h.status_code < 400 ? "text-emerald-700" : "text-amber-800"}>
                    {h.status_code ?? h.error_kind}
                  </span>
                  <span className="text-slate-400">{h.elapsed_ms} ms</span>
                </span>
                <span className="block truncate font-mono text-slate-600" title={h.url}>
                  {h.url.replace(/^https?:\/\//, "")}
                </span>
              </button>
              <button
                onClick={() => deleteHistory(h.id).then(refreshHistory)}
                className="text-slate-300 opacity-0 hover:text-rose-600 group-hover:opacity-100"
                title="Remove from history"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
