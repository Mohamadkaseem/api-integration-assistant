import type { Verification } from "@/lib/api";
import { VERIFICATION } from "@/lib/docs";

export function VerificationBadge({ value }: { value: Verification }) {
  const info = VERIFICATION[value];
  return (
    <span title={info.help} className={`inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${info.badge}`}>
      {info.label}
    </span>
  );
}
