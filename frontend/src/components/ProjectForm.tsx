"use client";

import { useState } from "react";

import type { ProjectInput } from "@/lib/api";
import { STATUS_OPTIONS } from "@/lib/projects";

type Props = {
  initial: ProjectInput;
  submitLabel: string;
  onSubmit: (data: ProjectInput) => Promise<void>;
  onCancel?: () => void;
};

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";

// One form used for both "New project" and "Edit project".
export function ProjectForm({ initial, submitLabel, onSubmit, onCancel }: Props) {
  const [data, setData] = useState<ProjectInput>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof ProjectInput>(field: K, value: ProjectInput[K]) {
    setData((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault(); // stop the browser from reloading the page
    if (!data.name.trim()) {
      setError("Please give the project a name.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({ ...data, name: data.name.trim() });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <label className="block text-sm font-medium text-slate-700">
        Project name *
        <input
          className={inputClass}
          value={data.name}
          onChange={(e) => update("name", e.target.value)}
          placeholder="e.g. HubSpot → Zoho CRM company sync"
          maxLength={200}
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block text-sm font-medium text-slate-700">
          Source application
          <input
            className={inputClass}
            value={data.source_app}
            onChange={(e) => update("source_app", e.target.value)}
            placeholder="e.g. HubSpot"
            maxLength={100}
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Target application
          <input
            className={inputClass}
            value={data.target_app}
            onChange={(e) => update("target_app", e.target.value)}
            placeholder="e.g. Zoho CRM"
            maxLength={100}
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Status
          <select
            className={inputClass}
            value={data.status}
            onChange={(e) => update("status", e.target.value as ProjectInput["status"])}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="block text-sm font-medium text-slate-700">
        Business requirement
        <textarea
          className={`${inputClass} min-h-32`}
          value={data.requirement}
          onChange={(e) => update("requirement", e.target.value)}
          placeholder="Describe the integration in plain language, as the client explained it."
        />
      </label>

      <label className="block text-sm font-medium text-slate-700">
        Notes
        <textarea
          className={`${inputClass} min-h-20`}
          value={data.notes}
          onChange={(e) => update("notes", e.target.value)}
          placeholder="Contacts, open questions, sandbox details (never paste passwords or tokens here)."
        />
      </label>

      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {saving ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
