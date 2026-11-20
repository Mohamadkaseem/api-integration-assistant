import { Suspense } from "react";

import { RequestBuilder } from "@/components/RequestBuilder";

export default function RequestBuilderPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
      <RequestBuilder />
    </Suspense>
  );
}
