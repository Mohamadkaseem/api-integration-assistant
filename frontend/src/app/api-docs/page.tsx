"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DocImporter } from "@/components/DocImporter";
import { getAIStatus, listDocs, listProjects, type AIStatus, type ApiDocSummary, type Project } from "@/lib/api";
import { SOURCE_LABEL, VERIFICATION } from "@/lib/docs";

export default function ApiDocsPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<ApiDocSummary[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);

  useEffect(() => {
    listDocs()
      .then(setDocs)
      .catch((err: Error) => setError(err.message));
    listProjects().then(setProjects).catch(() => setProjects([]));
    getAIStatus().then(setAIStatus).catch(() => setAIStatus(null));
  }, []);

  const projectName = (id: number | null) => projects.find((p) => p.id === id)?.name;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">API Doc Analyzer</h1>
        <p className="mt-1 text-slate-600">
          Import documentation once; every endpoint is stored with how far it can be trusted.
        </p>
      </div>

      <DocImporter projects={projects} aiStatus={aiStatus} onImported={(doc) => router.push(`/api-docs/${doc.id}`)} />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-900">Imported documentation</h2>
        {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {docs?.length === 0 && (
          <p className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
            Nothing imported yet.
          </p>
        )}
        <ul className="grid gap-3 lg:grid-cols-2">
          {docs?.map((doc) => (
            <li key={doc.id}>
              <Link
                href={`/api-docs/${doc.id}`}
                className="block h-full rounded-lg border border-slate-200 bg-white p-4 transition hover:border-indigo-300 hover:shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900">{doc.app_name}</p>
                    <p className="truncate text-sm text-slate-600">{doc.title || doc.source_ref}</p>
                  </div>
                  <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    {SOURCE_LABEL[doc.source_type] ?? doc.source_type}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-700">
                  <span className="font-semibold">{doc.endpoint_count}</span> endpoints
                  {(["spec", "quoted", "unverified"] as const)
                    .filter((v) => doc.counts[v])
                    .map((v) => (
                      <span key={v} className="ml-2 text-xs text-slate-500">
                        · {doc.counts[v]} {VERIFICATION[v].label.toLowerCase()}
                      </span>
                    ))}
                </p>
                {projectName(doc.project_id) && <p className="mt-1 text-xs text-indigo-700">{projectName(doc.project_id)}</p>}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
