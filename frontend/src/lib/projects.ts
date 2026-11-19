import type { ProjectInput, ProjectStatus } from "@/lib/api";

// Human-friendly labels and badge colours for each status.
export const STATUS_OPTIONS: { value: ProjectStatus; label: string; badge: string }[] = [
  { value: "planning", label: "Planning", badge: "bg-slate-100 text-slate-700" },
  { value: "in_progress", label: "In progress", badge: "bg-blue-50 text-blue-700" },
  { value: "testing", label: "Testing", badge: "bg-amber-50 text-amber-800" },
  { value: "completed", label: "Completed", badge: "bg-emerald-50 text-emerald-700" },
  { value: "on_hold", label: "On hold", badge: "bg-rose-50 text-rose-700" },
];

export function statusInfo(status: ProjectStatus) {
  return STATUS_OPTIONS.find((option) => option.value === status) ?? STATUS_OPTIONS[0];
}

export const EMPTY_PROJECT: ProjectInput = {
  name: "",
  source_app: "",
  target_app: "",
  requirement: "",
  status: "planning",
  notes: "",
};

export function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
