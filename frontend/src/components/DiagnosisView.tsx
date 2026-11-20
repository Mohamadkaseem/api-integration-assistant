"use client";

import { useRouter } from "next/navigation";

import type { Diagnosis, TroubleshootAnalysis, TroubleshootContext } from "@/lib/api";
import { fromCorrected, savePrefill } from "@/lib/prefill";

const CATEGORY_LABEL: Record<string, string> = {
  auth: "Authentication",
  permission: "Permission",
  validation: "Data / validation",
  not_found: "Not found",
  conflict: "Conflict / duplicate",
  rate_limit: "Rate limit",
  server: "Server problem",
  network: "Network",
  redirect: "Redirect",
  method: "Wrong method",
  unknown: "Other",
};

function List({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export function BuiltInDiagnosis({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-900">{diagnosis.title}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{CATEGORY_LABEL[diagnosis.category] ?? diagnosis.category}</span>
        {diagnosis.error_code && <span className="rounded bg-rose-50 px-1.5 py-0.5 font-mono text-xs text-rose-700">{diagnosis.error_code}</span>}
        {diagnosis.retryable && <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs text-sky-700">Retrying later may work</span>}
        <span className="ml-auto text-xs text-slate-400">built-in explanation · free</span>
      </div>
      <p className="text-slate-700">{diagnosis.explanation}</p>
      {diagnosis.error_message && (
        <p className="text-slate-600">
          Server says: <span className="italic">“{diagnosis.error_message}”</span>
        </p>
      )}
      {diagnosis.fields.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5">
          <span className="text-slate-600">Field{diagnosis.fields.length > 1 ? "s" : ""}:</span>
          {diagnosis.fields.map((f) => (
            <span key={f} className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-xs text-amber-900">
              {f}
            </span>
          ))}
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {diagnosis.likely_causes.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Likely causes</p>
            <List items={diagnosis.likely_causes} />
          </div>
        )}
        {diagnosis.suggestions.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">What to try</p>
            <List items={diagnosis.suggestions} />
          </div>
        )}
      </div>
    </div>
  );
}

const CONFIDENCE = { high: "bg-emerald-50 text-emerald-700", medium: "bg-amber-50 text-amber-800", low: "bg-rose-50 text-rose-700" };

export function AIAnalysisView({ analysis, context }: { analysis: TroubleshootAnalysis; context: TroubleshootContext }) {
  const router = useRouter();

  function openCorrected() {
    if (!analysis.corrected_request) return;
    savePrefill({
      request: fromCorrected(analysis.corrected_request),
      credential_id: context.credential_id,
      endpoint_id: context.endpoint_id,
      note: "Corrected request from the Error Troubleshooter — review it before sending.",
    });
    router.push(`/request-builder?prefill=${Date.now()}`); // unique value so the page reacts even if already open
  }

  return (
    <div className="space-y-3 rounded-lg border border-indigo-200 bg-indigo-50/40 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-900">Claude&apos;s analysis</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${CONFIDENCE[analysis.confidence]}`}>{analysis.confidence} confidence</span>
        {analysis.used_documentation && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">used imported docs</span>}
      </div>
      <p className="font-medium text-slate-900">{analysis.summary}</p>
      <p className="text-slate-700">
        <span className="font-medium">Cause:</span> {analysis.likely_cause}
        {analysis.field_at_fault && (
          <>
            {" "}
            · <span className="font-medium">Field:</span> <span className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-xs">{analysis.field_at_fault}</span>
          </>
        )}
      </p>
      <p className="text-slate-700">{analysis.explanation}</p>
      {analysis.fix_steps.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">How to fix</p>
          <ol className="list-decimal space-y-1 pl-5">
            {analysis.fix_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}
      {analysis.needs_more_info.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">To be sure, check</p>
          <List items={analysis.needs_more_info} />
        </div>
      )}
      {analysis.corrected_request && (
        <div className="space-y-2 rounded-md border border-slate-200 bg-white p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Corrected request</p>
          <p className="font-mono text-xs text-slate-800">
            {analysis.corrected_request.method} {analysis.corrected_request.url}
          </p>
          {analysis.corrected_request.changes.length > 0 && <List items={analysis.corrected_request.changes} />}
          {analysis.corrected_request.body && (
            <pre className="max-h-60 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{analysis.corrected_request.body}</pre>
          )}
          <button onClick={openCorrected} className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700">
            Open in Request Builder
          </button>
        </div>
      )}
    </div>
  );
}
