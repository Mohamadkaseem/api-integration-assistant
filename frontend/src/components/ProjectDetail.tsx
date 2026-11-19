"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ProjectForm } from "@/components/ProjectForm";
import { StatusBadge } from "@/components/StatusBadge";
import { deleteProject, getProject, updateProject, type Project, type ProjectInput } from "@/lib/api";
import { formatDate } from "@/lib/projects";

export function ProjectDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    getProject(projectId)
      .then(setProject)
      .catch((err: Error) => setError(err.message));
  }, [projectId]);

  async function handleSave(data: ProjectInput) {
    setProject(await updateProject(projectId, data));
    setEditing(false);
  }

  async function handleDelete() {
    // Deleting is permanent, so we always ask first.
    if (!project || !window.confirm(`Delete "${project.name}"? This cannot be undone.`)) return;
    try {
      await deleteProject(projectId);
      router.push("/projects");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the project.");
    }
  }

  return (
    <div className="space-y-6">
      <Link href="/projects" className="text-sm text-indigo-700 hover:underline">
        ← All projects
      </Link>

      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {!project && !error && <p className="text-sm text-slate-500">Loading project…</p>}

      {project && editing && (
        <>
          <h1 className="text-2xl font-semibold text-slate-900">Edit project</h1>
          <ProjectForm
            initial={project}
            submitLabel="Save changes"
            onSubmit={handleSave}
            onCancel={() => setEditing(false)}
          />
        </>
      )}

      {project && !editing && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">{project.name}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <StatusBadge status={project.status} />
                <span className="text-sm text-indigo-700">
                  {project.source_app || "—"} → {project.target_app || "—"}
                </span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href={`/requirements?project=${project.id}`}
                className="rounded-md border border-indigo-300 bg-white px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
              >
                Analyze requirement
              </Link>
              <button
                onClick={() => setEditing(true)}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Edit
              </button>
              <button
                onClick={handleDelete}
                className="rounded-md border border-rose-300 bg-white px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50"
              >
                Delete
              </button>
            </div>
          </div>

          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Business requirement</h2>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
              {project.requirement || "No requirement written yet."}
            </p>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Notes</h2>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{project.notes || "No notes."}</p>
          </section>

          <p className="text-xs text-slate-400">
            Created {formatDate(project.created_at)} · Updated {formatDate(project.updated_at)}
          </p>
        </>
      )}
    </div>
  );
}
