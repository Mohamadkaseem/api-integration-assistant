"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ProjectForm } from "@/components/ProjectForm";
import { StatusBadge } from "@/components/StatusBadge";
import { createProject, listProjects, type Project, type ProjectInput } from "@/lib/api";
import { EMPTY_PROJECT, formatDate } from "@/lib/projects";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(() => {
    listProjects()
      .then((data) => {
        setProjects(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  async function handleCreate(data: ProjectInput) {
    await createProject(data);
    setShowForm(false);
    load();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Projects</h1>
          <p className="mt-1 text-slate-600">Your integration projects. Open one to view or edit it.</p>
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            + New project
          </button>
        )}
      </div>

      {showForm && (
        <ProjectForm
          initial={EMPTY_PROJECT}
          submitLabel="Create project"
          onSubmit={handleCreate}
          onCancel={() => setShowForm(false)}
        />
      )}

      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {projects === null && !error && <p className="text-sm text-slate-500">Loading projects…</p>}
      {projects?.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          No projects yet. Click “New project” to add one.
        </p>
      )}

      <ul className="grid gap-4 lg:grid-cols-2">
        {projects?.map((project) => (
          <li key={project.id}>
            <Link
              href={`/projects/${project.id}`}
              className="block h-full rounded-lg border border-slate-200 bg-white p-5 transition hover:border-indigo-300 hover:shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-medium text-slate-900">{project.name}</h2>
                <StatusBadge status={project.status} />
              </div>
              {(project.source_app || project.target_app) && (
                <p className="mt-1 text-sm text-indigo-700">
                  {project.source_app || "—"} → {project.target_app || "—"}
                </p>
              )}
              {project.requirement && (
                <p className="mt-2 line-clamp-3 text-sm text-slate-600">{project.requirement}</p>
              )}
              <p className="mt-3 text-xs text-slate-400">Updated {formatDate(project.updated_at)}</p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
