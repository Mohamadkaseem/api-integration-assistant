import { Suspense } from "react";

import { RequirementAnalyzer } from "@/components/RequirementAnalyzer";

export default function RequirementsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
      <RequirementAnalyzer />
    </Suspense>
  );
}
