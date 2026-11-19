import { Suspense } from "react";

import { DocDetail } from "@/components/DocDetail";

export default function DocPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading documentation…</p>}>
      <DocDetail />
    </Suspense>
  );
}
