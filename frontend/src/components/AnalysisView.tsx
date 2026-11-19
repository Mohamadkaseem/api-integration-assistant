"use client";

import { useState } from "react";

import type { AnalysisResult, Clarification } from "@/lib/api";

const ACTION_STYLE: Record<string, string> = {
  read: "bg-sky-50 text-sky-700",
  search: "bg-sky-50 text-sky-700",
  create: "bg-emerald-50 text-emerald-700",
  update: "bg-amber-50 text-amber-800",
  upsert: "bg-amber-50 text-amber-800",
  delete: "bg-rose-50 text-rose-700",
  send: "bg-indigo-50 text-indigo-700",
  wait: "bg-slate-100 text-slate-700",
  decide: "bg-violet-50 text-violet-700",
};

const PRIORITY_STYLE = {
  high: "bg-rose-50 text-rose-700",
  medium: "bg-amber-50 text-amber-800",
  low: "bg-slate-100 text-slate-600",
};

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function BulletList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

type Props = {
  result: AnalysisResult;
  busy: boolean;
  onReanalyze: (clarifications: Clarification[]) => void;
};

export function AnalysisView({ result, busy, onReanalyze }: Props) {
  const { analysis } = result;
  const [answers, setAnswers] = useState<string[]>(() => analysis.clarification_questions.map(() => ""));
  const answeredCount = answers.filter((a) => a.trim()).length;

  function submitAnswers() {
    const newOnes = analysis.clarification_questions
      .map((q, i) => ({ question: q.question, answer: answers[i] ?? "" }))
      .filter((c) => c.answer.trim());
    // Keep earlier answers too, so the AI sees the whole conversation with the client.
    onReanalyze([...result.clarifications, ...newOnes]);
  }

  const ready = analysis.readiness === "ready_for_design";

  return (
    <div className="space-y-4">
      <div
        className={`rounded-lg border p-4 text-sm ${
          ready ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-900"
        }`}
      >
        <span className="font-semibold">{ready ? "Ready for design" : "Needs clarification"}</span>
        {" — "}
        {ready
          ? "the requirement is clear enough to start designing the integration."
          : "answer the questions below, then re-analyze."}
      </div>

      <Section title="Use case">
        <p className="text-sm text-slate-700">{analysis.summary}</p>
      </Section>

      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Trigger">
          <p className="text-sm text-slate-800">{analysis.trigger.event}</p>
          <p className="mt-1 text-xs text-slate-500">
            In <span className="font-medium text-slate-700">{analysis.trigger.app}</span> · detected by{" "}
            <span className="font-medium text-slate-700">{analysis.trigger.detection}</span>
          </p>
          {analysis.trigger.notes && <p className="mt-2 text-sm text-slate-600">{analysis.trigger.notes}</p>}
        </Section>
        <Section title="Applications">
          <p className="text-sm text-slate-700">
            <span className="text-slate-500">Source:</span> {analysis.source_app || "—"}
          </p>
          <p className="mt-1 text-sm text-slate-700">
            <span className="text-slate-500">Target:</span> {analysis.target_apps.join(", ") || "—"}
          </p>
        </Section>
      </div>

      <Section title="Steps" hint="Business-level sequence. API endpoints are added later from real documentation.">
        <ol className="space-y-3">
          {analysis.steps.map((step) => (
            <li key={step.order} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
                {step.order}
              </span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-slate-900">{step.app}</span>
                  <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${ACTION_STYLE[step.action] ?? "bg-slate-100 text-slate-700"}`}>
                    {step.action}
                  </span>
                </div>
                <p className="text-sm text-slate-700">{step.description}</p>
                {step.waits_for && <p className="text-xs text-violet-700">Waits for: {step.waits_for}</p>}
                {step.condition && <p className="text-xs text-amber-800">Only when: {step.condition}</p>}
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Data to transfer">
        {analysis.data_to_transfer.length === 0 ? (
          <p className="text-sm text-slate-500">None identified.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className="py-1 pr-4 font-medium">Data</th>
                  <th className="py-1 pr-4 font-medium">From</th>
                  <th className="py-1 pr-4 font-medium">To</th>
                  <th className="py-1 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {analysis.data_to_transfer.map((item, i) => (
                  <tr key={i}>
                    <td className="py-1.5 pr-4 font-medium text-slate-900">{item.name}</td>
                    <td className="py-1.5 pr-4">{item.from_app}</td>
                    <td className="py-1.5 pr-4">{item.to_app}</td>
                    <td className="py-1.5 text-slate-600">{item.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Conditions & business rules">
          <BulletList items={analysis.conditions} empty="None identified." />
        </Section>
        <Section title="Status updates">
          <BulletList items={analysis.status_updates} empty="No status updates required." />
        </Section>
      </div>

      <Section title="Expected outcome">
        <p className="text-sm text-slate-700">{analysis.expected_outcome}</p>
      </Section>

      <section className="rounded-lg border border-amber-200 bg-amber-50/50 p-5">
        <h3 className="text-sm font-semibold text-amber-900">Assumptions</h3>
        <p className="mt-0.5 text-xs text-amber-800">Not stated in the requirement — confirm these with the client.</p>
        <div className="mt-3">
          <BulletList items={analysis.assumptions} empty="No assumptions made." />
        </div>
      </section>

      <Section
        title={`Clarification questions (${analysis.clarification_questions.length})`}
        hint="Type the client's answers, then re-analyze. Leave a box empty to skip it."
      >
        {analysis.clarification_questions.length === 0 ? (
          <p className="text-sm text-slate-500">No open questions.</p>
        ) : (
          <div className="space-y-4">
            {analysis.clarification_questions.map((q, i) => (
              <div key={i}>
                <div className="flex items-start gap-2">
                  <span className={`mt-0.5 rounded px-1.5 py-0.5 text-xs font-medium ${PRIORITY_STYLE[q.priority]}`}>
                    {q.priority}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-slate-900">{q.question}</p>
                    <p className="text-xs text-slate-500">{q.why_it_matters}</p>
                  </div>
                </div>
                <textarea
                  className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  rows={2}
                  placeholder="Client's answer…"
                  value={answers[i] ?? ""}
                  onChange={(e) => setAnswers((current) => current.map((a, j) => (j === i ? e.target.value : a)))}
                />
              </div>
            ))}
            <button
              onClick={submitAnswers}
              disabled={busy || answeredCount === 0}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {busy ? "Analyzing…" : `Re-analyze with ${answeredCount} answer${answeredCount === 1 ? "" : "s"}`}
            </button>
          </div>
        )}
      </Section>

      {result.clarifications.length > 0 && (
        <Section title="Answers already included in this analysis">
          <ul className="space-y-2 text-sm">
            {result.clarifications.map((c, i) => (
              <li key={i}>
                <p className="font-medium text-slate-900">{c.question}</p>
                <p className="text-slate-700">{c.answer}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <p className="text-xs text-slate-400">
        Analyzed by {result.ai_model}
        {result.created_at ? ` · ${new Date(result.created_at).toLocaleString()}` : " · not saved (free-text mode)"}
      </p>
    </div>
  );
}
