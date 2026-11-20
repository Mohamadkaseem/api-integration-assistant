import { Suspense } from "react";

import { CredentialsManager } from "@/components/CredentialsManager";

export default function CredentialsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
      <CredentialsManager />
    </Suspense>
  );
}
