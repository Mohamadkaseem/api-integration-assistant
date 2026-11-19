import { Suspense } from "react";

import { ProjectDetail } from "@/components/ProjectDetail";

// The page itself is tiny: it shows a loading message while the
// client-side ProjectDetail component reads the project id from the URL.
export default function ProjectPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading project…</p>}>
      <ProjectDetail />
    </Suspense>
  );
}
