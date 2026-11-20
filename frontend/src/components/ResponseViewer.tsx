"use client";

import { useState } from "react";

import type { RunResult } from "@/lib/api";

function statusStyle(code: number | null) {
  if (code === null) return "bg-rose-100 text-rose-800";
  if (code < 300) return "bg-emerald-100 text-emerald-800";
  if (code < 400) return "bg-sky-100 text-sky-800";
  if (code < 500) return "bg-amber-100 text-amber-900";
  return "bg-rose-100 text-rose-800";
}

function prettyBody(body: string, contentType: string) {
  if (contentType.includes("json") || /^\s*[[{]/.test(body)) {
    try {
      return JSON.stringify(JSON.parse(body), null, 2);
    } catch {
      /* not JSON after all */
    }
  }
  return body;
}

function formatSize(bytes: number) {
  return bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ResponseViewer({ result }: { result: RunResult }) {
  const [tab, setTab] = useState<"body" | "headers">("body");

  if (!result.ok) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
        <p className="font-semibold">
          {result.error_kind === "blocked" ? "Request blocked" : result.error_kind === "invalid" ? "Request not sent" : "No response"}
        </p>
        <p className="mt-1">{result.error_message}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3 text-sm">
        <span className={`rounded px-2 py-0.5 font-semibold ${statusStyle(result.status_code)}`}>
          {result.status_code} {result.reason}
        </span>
        <span className="text-slate-500">{result.elapsed_ms} ms</span>
        <span className="text-slate-500">{formatSize(result.size_bytes)}</span>
        <div className="ml-auto flex gap-1 text-xs">
          {(["body", "headers"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`rounded px-2 py-1 ${tab === t ? "bg-slate-100 font-medium text-slate-900" : "text-slate-500"}`}>
              {t === "body" ? "Body" : `Headers (${Object.keys(result.headers).length})`}
            </button>
          ))}
        </div>
      </div>
      {result.status_code !== null && result.status_code >= 300 && result.status_code < 400 && result.headers.location && (
        <p className="border-b border-slate-100 bg-sky-50 px-4 py-2 text-xs text-sky-800">
          Redirect to <span className="font-mono">{result.headers.location}</span> — not followed automatically.
        </p>
      )}
      {tab === "body" ? (
        result.is_binary ? (
          <p className="p-4 text-sm text-slate-600">Binary content ({result.content_type || "unknown type"}, {formatSize(result.size_bytes)}) — not shown.</p>
        ) : (
          <>
            {result.body_truncated && <p className="px-4 pt-3 text-xs text-amber-800">Response larger than 5 MB — only the first part is shown.</p>}
            <pre className="max-h-[32rem] overflow-auto p-4 font-mono text-xs text-slate-800">{prettyBody(result.body, result.content_type) || "(empty body)"}</pre>
          </>
        )
      ) : (
        <table className="w-full text-left text-xs">
          <tbody className="divide-y divide-slate-100">
            {Object.entries(result.headers).map(([k, v]) => (
              <tr key={k}>
                <td className="px-4 py-1.5 font-mono font-medium text-slate-700">{k}</td>
                <td className="break-all px-4 py-1.5 font-mono text-slate-600">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
