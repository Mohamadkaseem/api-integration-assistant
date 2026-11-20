"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { MermaidDiagram } from "@/components/MermaidDiagram";
import {
  designFromAnalysis,
  getAIStatus,
  getDesign,
  listProjects,
  matchEndpointsAI,
  saveDesign,
  suggestMappingsAI,
  type AIStatus,
  type Design,
  type DesignStep,
  type FieldMapping,
  type Project,
} from "@/lib/api";

type Tab = "steps" | "mapping" | "workflow";
const ACTIONS = ["read", "search", "create", "update", "upsert", "delete", "send", "wait", "decide", "notify", "log", "other"];
const ISSUES: FieldMapping["issue"][] = ["none", "type", "date", "picklist", "nested", "required", "unknown"];
const cell = "w-full rounded border border-slate-300 bg-white px-2 py-1 text-xs focus:border-indigo-500 focus:outline-none";

const MATCH_BADGE: Record<DesignStep["match_status"], string> = {
  matched: "bg-sky-50 text-sky-700",
  manual: "bg-emerald-50 text-emerald-700",
  no_endpoint: "bg-amber-50 text-amber-800",
  unmatched: "bg-slate-100 text-slate-500",
};
const MATCH_LABEL: Record<DesignStep["match_status"], string> = {
  matched: "AI match",
  manual: "chosen by you",
  no_endpoint: "no documented endpoint",
  unmatched: "—",
};
const EVIDENCE_BADGE = { documented: "bg-emerald-50 text-emerald-700", assumed: "bg-amber-50 text-amber-800", manual: "bg-slate-100 text-slate-600" };

const EMPTY_STEP = (order: number): DesignStep => ({
  order, app: "", action: "other", description: "", condition: "", waits_for: "", endpoint_id: null, endpoint_label: "", match_status: "unmatched", match_note: "",
});
const EMPTY_MAPPING: FieldMapping = {
  source_app: "", source_field: "", target_app: "", target_field: "", transform: "", required: false, issue: "none", notes: "", evidence: "manual",
};

export function IntegrationDesign({ defaultTab }: { defaultTab: Tab }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const projectId = Number(searchParams.get("project")) || null;
  const [tab, setTab] = useState<Tab>((searchParams.get("tab") as Tab) || defaultTab);
  const [design, setDesign] = useState<Design | null>(null);
  const [trigger, setTrigger] = useState("");
  const [docIds, setDocIds] = useState<number[]>([]);
  const [steps, setSteps] = useState<DesignStep[]>([]);
  const [mappings, setMappings] = useState<FieldMapping[]>([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);

  const apply = useCallback((d: Design) => {
    setDesign(d);
    setTrigger(d.trigger);
    setDocIds(d.doc_ids);
    setSteps(d.steps);
    setMappings(d.mappings);
    setDirty(false);
  }, []);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]));
    getAIStatus().then(setAIStatus).catch(() => setAIStatus(null));
  }, []);

  useEffect(() => {
    if (!projectId) return;
    getDesign(projectId)
      .then(apply)
      .catch((err: Error) => setError(err.message));
  }, [projectId, apply]);

  const edit = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setDirty(true);
  };
  const setStepsDirty = edit(setSteps);
  const setMappingsDirty = edit(setMappings);

  async function run(label: string, action: () => Promise<Design>, saveFirst = true) {
    if (!projectId) return;
    setBusy(label);
    setError(null);
    try {
      if (saveFirst && dirty) await saveDesign(projectId, { trigger, doc_ids: docIds, steps, mappings });
      apply(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed.");
    } finally {
      setBusy(null);
    }
  }

  const save = () => run("save", () => saveDesign(projectId!, { trigger, doc_ids: docIds, steps, mappings }), false);
  const updateStep = (i: number, patch: Partial<DesignStep>) => setStepsDirty(steps.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const moveStep = (i: number, delta: number) => {
    const next = [...steps];
    const [item] = next.splice(i, 1);
    next.splice(i + delta, 0, item);
    setStepsDirty(next.map((s, j) => ({ ...s, order: j + 1 })));
  };
  const updateMapping = (i: number, patch: Partial<FieldMapping>) =>
    setMappingsDirty(mappings.map((m, j) => (j === i ? { ...m, ...patch, evidence: "manual" } : m)));

  const aiMissing = aiStatus !== null && !aiStatus.configured;
  const endpointsInSelected = design?.endpoints.filter((e) => docIds.includes(e.doc_id)) ?? [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Integration Design</h1>
          <p className="mt-1 text-slate-600">Steps with real endpoints, field mapping and the workflow diagram — per project.</p>
        </div>
        <select
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          value={projectId ?? ""}
          onChange={(e) => router.push(`?project=${e.target.value}&tab=${tab}`)}
        >
          <option value="">Choose a project…</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {!projectId && <p className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">Choose a project to design its integration.</p>}
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      {projectId && design && (
        <>
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-200">
            {(
              [
                ["steps", `Steps & endpoints (${steps.length})`],
                ["mapping", `Field mapping (${mappings.length})`],
                ["workflow", "Workflow diagram"],
              ] as [Tab, string][]
            ).map(([value, label]) => (
              <button key={value} onClick={() => setTab(value)} className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === value ? "border-indigo-600 font-medium text-slate-900" : "border-transparent text-slate-500"}`}>
                {label}
              </button>
            ))}
            <div className="ml-auto flex items-center gap-3 pb-1">
              {dirty && <span className="text-xs text-amber-700">Unsaved changes</span>}
              <button onClick={save} disabled={!dirty || busy !== null} className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">
                {busy === "save" ? "Saving…" : "Save"}
              </button>
            </div>
          </div>

          {aiMissing && (
            <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Claude is not connected — AI buttons are disabled. Everything else (manual steps, endpoints, mappings, diagram) works.
            </p>
          )}

          {tab === "steps" && (
            <div className="space-y-4">
              <section className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 lg:grid-cols-2">
                <label className="block text-sm font-medium text-slate-700">
                  Trigger
                  <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={trigger} onChange={(e) => edit(setTrigger)(e.target.value)} placeholder="e.g. New company created in HubSpot" />
                </label>
                <div className="text-sm">
                  <p className="font-medium text-slate-700">Documentation to use</p>
                  {design.available_docs.length === 0 && (
                    <p className="mt-1 text-xs text-slate-500">
                      None imported yet — <Link href="/api-docs" className="text-indigo-700 underline">import docs</Link> to choose real endpoints.
                    </p>
                  )}
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                    {design.available_docs.map((d) => (
                      <label key={d.id} className="flex items-center gap-1.5 text-xs text-slate-700">
                        <input
                          type="checkbox"
                          checked={docIds.includes(d.id)}
                          onChange={(e) => edit(setDocIds)(e.target.checked ? [...docIds, d.id] : docIds.filter((x) => x !== d.id))}
                        />
                        {d.app_name} — {d.title} ({d.endpoint_count}){d.linked_to_project ? " ★" : ""}
                      </label>
                    ))}
                  </div>
                  {dirty && <p className="mt-1 text-xs text-slate-500">Save to refresh the endpoint list after changing documentation.</p>}
                </div>
              </section>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => window.confirm("Replace the current steps with the steps from the latest requirement analysis?") && run("analysis", () => designFromAnalysis(projectId), false)}
                  disabled={busy !== null || !design.has_analysis}
                  title={design.has_analysis ? "" : "Analyze this project in the Requirement Analyzer first"}
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {busy === "analysis" ? "Loading…" : "Create steps from requirement analysis"}
                </button>
                <button
                  onClick={() => run("match", () => matchEndpointsAI(projectId))}
                  disabled={busy !== null || aiMissing || steps.length === 0 || docIds.length === 0}
                  className="rounded-md border border-indigo-300 bg-white px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                >
                  {busy === "match" ? "Claude is matching…" : "Match endpoints with AI"}
                </button>
                {!design.has_analysis && <span className="self-center text-xs text-slate-500">No requirement analysis yet — add steps manually or analyze the project first.</span>}
              </div>

              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full min-w-[60rem] text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="w-8 px-2 py-2">#</th>
                      <th className="w-28 px-2 py-2">App</th>
                      <th className="w-24 px-2 py-2">Action</th>
                      <th className="px-2 py-2">Description</th>
                      <th className="w-40 px-2 py-2">Only when / waits for</th>
                      <th className="w-72 px-2 py-2">Endpoint</th>
                      <th className="w-16 px-2 py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 align-top">
                    {steps.map((s, i) => (
                      <tr key={i}>
                        <td className="px-2 py-2 font-semibold text-slate-500">{i + 1}</td>
                        <td className="px-2 py-2"><input className={cell} value={s.app} onChange={(e) => updateStep(i, { app: e.target.value })} /></td>
                        <td className="px-2 py-2">
                          <select className={cell} value={s.action} onChange={(e) => updateStep(i, { action: e.target.value })}>
                            {ACTIONS.map((a) => <option key={a}>{a}</option>)}
                          </select>
                        </td>
                        <td className="px-2 py-2"><textarea className={cell} rows={2} value={s.description} onChange={(e) => updateStep(i, { description: e.target.value })} /></td>
                        <td className="space-y-1 px-2 py-2">
                          <input className={cell} value={s.condition} onChange={(e) => updateStep(i, { condition: e.target.value })} placeholder="only when…" />
                          <input className={cell} value={s.waits_for} onChange={(e) => updateStep(i, { waits_for: e.target.value })} placeholder="waits for…" />
                        </td>
                        <td className="space-y-1 px-2 py-2">
                          <select
                            className={cell}
                            value={s.endpoint_id ?? ""}
                            onChange={(e) => updateStep(i, e.target.value ? { endpoint_id: Number(e.target.value), match_status: "manual", match_note: "" } : { endpoint_id: null, match_status: "unmatched", endpoint_label: "" })}
                          >
                            <option value="">No endpoint / not an API call</option>
                            {endpointsInSelected.map((ep) => (
                              <option key={ep.id} value={ep.id}>
                                {ep.app_name}: {ep.method} {ep.path}{ep.verification === "unverified" ? " ⚠" : ""}
                              </option>
                            ))}
                          </select>
                          <span className={`inline-block rounded px-1.5 py-0.5 ${MATCH_BADGE[s.match_status]}`}>{MATCH_LABEL[s.match_status]}</span>
                          {s.match_note && <p className="text-slate-500">{s.match_note}</p>}
                        </td>
                        <td className="whitespace-nowrap px-2 py-2 text-slate-400">
                          <button disabled={i === 0} onClick={() => moveStep(i, -1)} className="px-1 hover:text-slate-700 disabled:opacity-30" title="Move up">↑</button>
                          <button disabled={i === steps.length - 1} onClick={() => moveStep(i, 1)} className="px-1 hover:text-slate-700 disabled:opacity-30" title="Move down">↓</button>
                          <button onClick={() => setStepsDirty(steps.filter((_, j) => j !== i).map((x, j) => ({ ...x, order: j + 1 })))} className="px-1 hover:text-rose-600" title="Remove">✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button onClick={() => setStepsDirty([...steps, EMPTY_STEP(steps.length + 1)])} className="m-3 text-xs font-medium text-indigo-700 hover:underline">
                  + Add step
                </button>
              </div>

              {design.missing_documentation.length > 0 && (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <p className="font-semibold">Documentation still needed</p>
                  <ul className="mt-1 list-disc pl-5">
                    {design.missing_documentation.map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                </section>
              )}
            </div>
          )}

          {tab === "mapping" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => run("mapping", () => suggestMappingsAI(projectId))}
                  disabled={busy !== null || aiMissing || !steps.some((s) => s.endpoint_id)}
                  className="rounded-md border border-indigo-300 bg-white px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                >
                  {busy === "mapping" ? "Claude is mapping…" : "Suggest mappings with AI"}
                </button>
                <span className="text-xs text-slate-500">
                  Uses the documentation of the endpoints chosen in Steps. Your own rows are kept. Fields not found in the docs are marked “assumed”.
                </span>
              </div>
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full min-w-[64rem] text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="px-2 py-2">Source app</th>
                      <th className="px-2 py-2">Source field</th>
                      <th className="px-2 py-2"></th>
                      <th className="px-2 py-2">Target app</th>
                      <th className="px-2 py-2">Target field</th>
                      <th className="px-2 py-2">Transformation</th>
                      <th className="px-2 py-2">Req.</th>
                      <th className="px-2 py-2">Issue</th>
                      <th className="px-2 py-2">Source</th>
                      <th className="px-2 py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {mappings.map((m, i) => (
                      <tr key={i} className="align-top">
                        <td className="w-28 px-2 py-2"><input className={cell} value={m.source_app} onChange={(e) => updateMapping(i, { source_app: e.target.value })} /></td>
                        <td className="px-2 py-2"><input className={`${cell} font-mono`} value={m.source_field} onChange={(e) => updateMapping(i, { source_field: e.target.value })} /></td>
                        <td className="px-1 py-2 text-slate-400">→</td>
                        <td className="w-28 px-2 py-2"><input className={cell} value={m.target_app} onChange={(e) => updateMapping(i, { target_app: e.target.value })} /></td>
                        <td className="px-2 py-2"><input className={`${cell} font-mono`} value={m.target_field} onChange={(e) => updateMapping(i, { target_field: e.target.value })} /></td>
                        <td className="px-2 py-2">
                          <input className={cell} value={m.transform} onChange={(e) => updateMapping(i, { transform: e.target.value })} placeholder="e.g. format date" />
                          {m.notes && <p className="mt-1 text-slate-500">{m.notes}</p>}
                        </td>
                        <td className="px-2 py-2 text-center"><input type="checkbox" checked={m.required} onChange={(e) => updateMapping(i, { required: e.target.checked })} /></td>
                        <td className="w-24 px-2 py-2">
                          <select className={cell} value={m.issue} onChange={(e) => updateMapping(i, { issue: e.target.value as FieldMapping["issue"] })}>
                            {ISSUES.map((x) => <option key={x}>{x}</option>)}
                          </select>
                        </td>
                        <td className="px-2 py-2"><span className={`rounded px-1.5 py-0.5 ${EVIDENCE_BADGE[m.evidence]}`}>{m.evidence}</span></td>
                        <td className="px-2 py-2">
                          <button onClick={() => setMappingsDirty(mappings.filter((_, j) => j !== i))} className="text-slate-400 hover:text-rose-600" title="Remove">✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {mappings.length === 0 && <p className="px-4 py-6 text-center text-sm text-slate-500">No mappings yet. Add rows yourself or let Claude suggest them.</p>}
                <button onClick={() => setMappingsDirty([...mappings, { ...EMPTY_MAPPING }])} className="m-3 text-xs font-medium text-indigo-700 hover:underline">
                  + Add mapping
                </button>
              </div>
              <p className="text-xs text-slate-500">
                <span className="rounded bg-emerald-50 px-1 text-emerald-700">documented</span> both fields found in the imported docs ·{" "}
                <span className="rounded bg-amber-50 px-1 text-amber-800">assumed</span> not found — confirm before building ·{" "}
                <span className="rounded bg-slate-100 px-1">manual</span> entered or edited by you
              </p>
            </div>
          )}

          {tab === "workflow" && (
            <div className="space-y-3">
              {dirty && <p className="text-xs text-amber-700">Showing the last saved version — save to update the diagram.</p>}
              {steps.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">Add steps to see the workflow.</p>
              ) : (
                <MermaidDiagram text={design.mermaid} />
              )}
              <details className="text-xs text-slate-600">
                <summary className="cursor-pointer">Mermaid source (paste into docs, Confluence, GitHub…)</summary>
                <pre className="mt-2 overflow-x-auto rounded bg-slate-900 p-3 text-slate-100">{design.mermaid}</pre>
              </details>
            </div>
          )}
        </>
      )}
    </div>
  );
}
