"use client";

import { useEffect, useState } from "react";

import { TroubleshootPanel } from "@/components/TroubleshootPanel";
import { listHistory, type HistoryItem, type TroubleshootInput } from "@/lib/api";

const input = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";

export default function TroubleshooterPage() {
  const [mode, setMode] = useState<"paste" | "history">("paste");
  const [status, setStatus] = useState("");
  const [responseBody, setResponseBody] = useState("");
  const [method, setMethod] = useState("POST");
  const [url, setUrl] = useState("");
  const [requestBody, setRequestBody] = useState("");
  const [failed, setFailed] = useState<HistoryItem[]>([]);
  const [current, setCurrent] = useState<TroubleshootInput | null>(null);

  useEffect(() => {
    listHistory()
      .then((items) => setFailed(items.filter((h) => h.status_code === null || h.status_code >= 400)))
      .catch(() => setFailed([]));
  }, []);

  function analyzePasted(event: React.FormEvent) {
    event.preventDefault();
    setCurrent({
      status_code: status ? Number(status) : null,
      response_body: responseBody,
      request: url || requestBody ? { method, url, headers: [], body_type: requestBody.trim() ? "json" : "none", body: requestBody } : undefined,
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Error Troubleshooter</h1>
        <p className="mt-1 text-slate-600">Understand an API error and how to fix it. Built-in explanations are instant and free; Claude can go deeper.</p>
      </div>

      <div className="flex gap-1 rounded-md bg-slate-100 p-1 text-sm">
        {(
          [
            ["paste", "Paste an error"],
            ["history", `Failed requests (${failed.length})`],
          ] as const
        ).map(([value, label]) => (
          <button key={value} onClick={() => setMode(value)} className={`rounded px-3 py-1.5 ${mode === value ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}>
            {label}
          </button>
        ))}
      </div>

      {mode === "paste" && (
        <form onSubmit={analyzePasted} className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
          <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
            <label className="block text-sm font-medium text-slate-700">
              Status code
              <input className={input} value={status} onChange={(e) => setStatus(e.target.value.replace(/\D/g, "").slice(0, 3))} placeholder="e.g. 400" inputMode="numeric" />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Error response *
              <textarea className={`${input} min-h-28 font-mono text-xs`} value={responseBody} onChange={(e) => setResponseBody(e.target.value)}
                placeholder='{"code": "INVALID_DATA", "message": "Invalid value for field"}' />
            </label>
          </div>
          <details className="text-sm">
            <summary className="cursor-pointer text-slate-600">Add the request that caused it (optional, helps the AI suggest a corrected request)</summary>
            <div className="mt-3 space-y-3">
              <div className="flex gap-2">
                <select className="rounded-md border border-slate-300 px-2 text-sm" value={method} onChange={(e) => setMethod(e.target.value)}>
                  {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
                <input className={`${input} mt-0 font-mono`} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.zohoapis.in/crm/v3/Accounts" />
              </div>
              <textarea className={`${input} min-h-24 font-mono text-xs`} value={requestBody} onChange={(e) => setRequestBody(e.target.value)} placeholder="Request body (JSON)" />
              <p className="text-xs text-slate-500">Don&apos;t paste tokens or passwords here; if any are included, they are masked before anything is analyzed.</p>
            </div>
          </details>
          <button type="submit" disabled={!responseBody.trim() && !status} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            Explain this error
          </button>
        </form>
      )}

      {mode === "history" && (
        <div className="rounded-lg border border-slate-200 bg-white">
          {failed.length === 0 && <p className="p-5 text-sm text-slate-500">No failed requests in your history.</p>}
          <ul className="divide-y divide-slate-100">
            {failed.map((h) => (
              <li key={h.id}>
                <button onClick={() => setCurrent({ history_id: h.id })} className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-slate-50 ${current?.history_id === h.id ? "bg-indigo-50" : ""}`}>
                  <span className="w-14 font-bold text-slate-700">{h.method}</span>
                  <span className="w-20 text-rose-700">{h.status_code ?? h.error_kind}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-600">{h.url}</span>
                  <span className="text-xs text-slate-400">{new Date(h.created_at).toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {current && <TroubleshootPanel input={current} />}
    </div>
  );
}
