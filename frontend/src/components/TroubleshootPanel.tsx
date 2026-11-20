"use client";

import { useEffect, useState } from "react";

import { AIAnalysisView, BuiltInDiagnosis } from "@/components/DiagnosisView";
import {
  explainError,
  explainErrorWithAI,
  getAIStatus,
  type AIStatus,
  type Diagnosis,
  type TroubleshootAnalysis,
  type TroubleshootContext,
  type TroubleshootInput,
} from "@/lib/api";

// Shows the free built-in explanation immediately, with an optional "Explain with AI" step.
export function TroubleshootPanel({ input }: { input: TroubleshootInput }) {
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [context, setContext] = useState<TroubleshootContext | null>(null);
  const [analysis, setAnalysis] = useState<TroubleshootAnalysis | null>(null);
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(input);

  useEffect(() => {
    explainError(input)
      .then((r) => {
        setDiagnosis(r.diagnosis);
        setContext(r.context);
        setAnalysis(null);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
    getAIStatus().then(setAIStatus).catch(() => setAIStatus(null));
    // `key` captures the input's content
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  async function askAI() {
    setBusy(true);
    setError(null);
    try {
      const r = await explainErrorWithAI(input);
      setAnalysis(r.analysis);
      setContext(r.context);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {diagnosis && <BuiltInDiagnosis diagnosis={diagnosis} />}
      {diagnosis && !analysis && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={askAI}
            disabled={busy || (aiStatus !== null && !aiStatus.configured)}
            className="rounded-md border border-indigo-300 bg-white px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
          >
            {busy ? "Claude is analyzing…" : "Explain with AI + suggest a fix"}
          </button>
          <span className="text-xs text-slate-500">
            {aiStatus && !aiStatus.configured
              ? "Needs your Claude API key (see Requirement Analyzer)."
              : "Sends the request and response with secrets masked; a few cents per analysis."}
          </span>
        </div>
      )}
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {analysis && context && <AIAnalysisView analysis={analysis} context={context} />}
    </div>
  );
}
