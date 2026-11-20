"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AnalysisView } from "@/components/AnalysisView";
import {
  analyzeRequirement,
  getAIStatus,
  getLatestAnalysis,
  listProjects,
  type AIStatus,
  type AnalysisResult,
  type Clarification,
  type Project,
} from "@/lib/api";

const FREE_TEXT = "free";

export function RequirementAnalyzer() {
  const searchParams = useSearchParams();
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<string>(FREE_TEXT);
  const [requirement, setRequirement] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const projectId = selected === FREE_TEXT ? null : Number(selected);

  // Choosing a project loads its requirement and its latest saved analysis.
  function selectProject(value: string, projectList: Project[]) {
    setSelected(value);
    setResult(null);
    setError(null);
    if (value === FREE_TEXT) return;
    const id = Number(value);
    const project = projectList.find((p) => p.id === id);
    if (project) setRequirement(project.requirement);
    getLatestAnalysis(id)
      .then(setResult)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    getAIStatus().then(setAIStatus).catch(() => setAIStatus(null));
    listProjects()
      .then((list) => {
        setProjects(list);
        // Opened from a project page (/requirements?project=3): select that project.
        const fromUrl = searchParams.get("project");
        if (fromUrl) selectProject(fromUrl, list);
      })
      .catch((err: Error) => setError(err.message));
    // Runs once when the page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(clarifications: Clarification[]) {
    setBusy(true);
    setError(null);
    try {
      setResult(await analyzeRequirement({ requirement, clarifications, project_id: projectId }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  const tooShort = requirement.trim().length < 10;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Requirement Analyzer</h1>
        <p className="mt-1 text-slate-600">
          Claude turns a plain-language requirement into trigger, apps, steps, data, conditions — and asks what is
          missing.
        </p>
      </div>

      {aiStatus && !aiStatus.configured && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">Claude is not connected yet</p>
          <p className="mt-1">{aiStatus.hint}</p>
        </div>
      )}

      <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <label className="block text-sm font-medium text-slate-700">
          Project
          <select
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            value={selected}
            onChange={(e) => selectProject(e.target.value, projects)}
          >
            <option value={FREE_TEXT}>Quick analysis — free text (not saved)</option>
            {projects.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Requirement
          <textarea
            className="mt-1 min-h-36 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="e.g. Sync HubSpot companies into Zoho CRM Accounts. If the account exists, update it. Otherwise, create a new account."
          />
        </label>
        {projectId !== null && (
          <p className="text-xs text-slate-500">
            Changes here are used for this analysis only. To change the project&apos;s saved requirement,{" "}
            <Link href={`/projects/${projectId}`} className="text-indigo-700 hover:underline">
              edit the project
            </Link>
            .
          </p>
        )}

        <button
          onClick={() => run([])}
          disabled={busy || tooShort}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy ? "Analyzing…" : result ? "Analyze again (fresh)" : "Analyze requirement"}
        </button>
        {busy && <p className="text-sm text-slate-500">Claude is reading the requirement. This usually takes 20–60 seconds.</p>}
      </div>

      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      {result && <AnalysisView key={`${result.id}-${result.created_at}`} result={result} busy={busy} onReanalyze={run} />}
    </div>
  );
}
