"use client";

import { useState } from "react";

import { importDoc, type AIStatus, type ApiDocDetail, type Project } from "@/lib/api";

type Mode = "file" | "text" | "url";

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";

const MODES: { value: Mode; label: string; help: string }[] = [
  { value: "file", label: "Upload file", help: "OpenAPI / Swagger (.json, .yaml), Postman collection (.json), PDF, or text file." },
  { value: "text", label: "Paste text", help: "Copy documentation text from a web page or email and paste it here." },
  { value: "url", label: "From URL", help: "A public link to a spec file, a documentation page, or a PDF." },
];

function formatSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Spec files are read by code; everything else needs Claude.
function needsAI(mode: Mode, file: File | null) {
  if (mode === "text") return true;
  if (mode === "file" && file) return !/\.(json|ya?ml)$/i.test(file.name);
  return false; // URLs: unknown until downloaded
}

type ImporterProps = { projects: Project[]; aiStatus: AIStatus | null; onImported: (doc: ApiDocDetail) => void };

export function DocImporter({ projects, aiStatus, onImported }: ImporterProps) {
  const [mode, setMode] = useState<Mode>("file");
  const [appName, setAppName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sourceReady = mode === "file" ? file !== null : mode === "text" ? text.trim().length > 0 : url.trim().length > 0;
  const aiMissing = aiStatus !== null && !aiStatus.configured;
  const blockedByAI = aiMissing && needsAI(mode, file);

  // Tell the user exactly why the button is disabled.
  let blocker = "";
  if (!appName.trim()) blocker = "Enter the application name (e.g. Zoho Sign).";
  else if (!sourceReady)
    blocker = mode === "file" ? "Choose a file." : mode === "text" ? "Paste the documentation text." : "Enter a URL.";
  else if (blockedByAI)
    blocker = "PDFs, text and web pages are read by Claude, which is not connected yet. Spec files (.json, .yaml) work without it.";

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

      {/* All three inputs stay on the page (only hidden), so switching tabs never loses your file or text. */}
      <div className={mode === "file" ? "space-y-2" : "hidden"}>
        <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center hover:border-indigo-400 hover:bg-indigo-50/40">
          <span className="text-sm font-medium text-indigo-700">{file ? "Choose a different file" : "Click to choose a file"}</span>
          <span className="mt-1 text-xs text-slate-500">.json · .yaml · .pdf · .txt · .html — up to 30 MB</span>
          <input
            type="file"
            accept=".json,.yaml,.yml,.pdf,.txt,.md,.html,.htm"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              e.target.value = ""; // allows choosing the same file again later
            }}
            className="sr-only"
          />
        </label>
        {file && (
          <div className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
            <span className="min-w-0 truncate">
              <span className="font-medium text-slate-900">{file.name}</span>{" "}
              <span className="text-slate-500">({formatSize(file.size)})</span>
            </span>
            <button type="button" onClick={() => setFile(null)} className="shrink-0 text-xs font-medium text-rose-700 hover:underline">
              Remove
            </button>
          </div>
        )}
      </div>
      <textarea
        className={mode === "text" ? `${inputClass} min-h-48 font-mono` : "hidden"}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste API documentation here…"
      />
      <input className={mode === "url" ? inputClass : "hidden"} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" type="url" />

      {aiMissing && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Claude is not connected: OpenAPI / Postman files (.json, .yaml) import normally; PDFs, pasted text and web pages need your API key.{" "}
          {aiStatus?.hint}
        </p>
      )}

      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={busy || blocker !== ""}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy ? "Importing…" : "Import documentation"}
        </button>
        {!busy && blocker && <p className="text-sm text-slate-500">{blocker}</p>}
        {busy && (
          <p className="text-sm text-slate-500">
            Spec files take seconds. PDFs, pages and text are read by Claude and can take 1–3 minutes.
          </p>
        )}
      </div>
    </form>
  );
}
