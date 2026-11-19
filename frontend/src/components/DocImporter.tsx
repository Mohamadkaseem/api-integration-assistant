"use client";

import { useState } from "react";

import { importDoc, type ApiDocDetail, type Project } from "@/lib/api";

type Mode = "file" | "text" | "url";

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";

const MODES: { value: Mode; label: string; help: string }[] = [
  { value: "file", label: "Upload file", help: "OpenAPI / Swagger (.json, .yaml), Postman collection (.json), PDF, or text file." },
  { value: "text", label: "Paste text", help: "Copy documentation text from a web page or email and paste it here." },
  { value: "url", label: "From URL", help: "A public link to a spec file, a documentation page, or a PDF." },
];

export function DocImporter({ projects, onImported }: { projects: Project[]; onImported: (doc: ApiDocDetail) => void }) {
  const [mode, setMode] = useState<Mode>("file");
  const [appName, setAppName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sourceReady = mode === "file" ? file !== null : mode === "text" ? text.trim().length > 0 : url.trim().length > 0;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("app_name", appName.trim());
    if (projectId) form.append("project_id", projectId);
    if (mode === "file" && file) form.append("file", file);
    if (mode === "text") form.append("text", text);
    if (mode === "url") form.append("url", url.trim());
    try {
      onImported(await importDoc(form));
      setFile(null);
      setText("");
      setUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-medium text-slate-700">
          Application *
          <input className={inputClass} value={appName} onChange={(e) => setAppName(e.target.value)} placeholder="e.g. Zoho Sign" maxLength={100} />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Project (optional)
          <select className={inputClass} value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">Not linked to a project</option>
            {projects.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div>
        <div className="flex flex-wrap gap-1 rounded-md bg-slate-100 p-1 text-sm">
          {MODES.map((m) => (
            <button
              key={m.value}
              type="button"
              onClick={() => setMode(m.value)}
              className={`rounded px-3 py-1.5 ${mode === m.value ? "bg-white font-medium text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">{MODES.find((m) => m.value === mode)?.help}</p>
      </div>

      {mode === "file" && (
        <input
          type="file"
          accept=".json,.yaml,.yml,.pdf,.txt,.md,.html,.htm"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
        />
      )}
      {mode === "text" && (
        <textarea className={`${inputClass} min-h-48 font-mono`} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste API documentation here…" />
      )}
      {mode === "url" && (
        <input className={inputClass} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" type="url" />
      )}

      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={busy || !appName.trim() || !sourceReady}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy ? "Importing…" : "Import documentation"}
        </button>
        {busy && (
          <p className="text-sm text-slate-500">
            Spec files take seconds. PDFs, pages and text are read by Claude and can take 1–3 minutes.
          </p>
        )}
      </div>
    </form>
  );
}
