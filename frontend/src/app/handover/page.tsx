import { Suspense } from "react";

import { HandoverDocs } from "@/components/HandoverDocs";

export default function HandoverPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
      <HandoverDocs />
    </Suspense>
  );
}
