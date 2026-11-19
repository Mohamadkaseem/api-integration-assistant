import type { ProjectStatus } from "@/lib/api";
import { statusInfo } from "@/lib/projects";

export function StatusBadge({ status }: { status: ProjectStatus }) {
  const info = statusInfo(status);
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${info.badge}`}>
      {info.label}
    </span>
  );
}
