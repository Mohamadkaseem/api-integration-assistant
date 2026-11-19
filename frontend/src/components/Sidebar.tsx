import { Suspense } from "react";

import { ActiveNavLinks } from "@/components/ActiveNavLinks";
import { NavLinks } from "@/components/NavLinks";

export function Sidebar() {
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-slate-200 bg-white md:h-screen md:w-64 md:border-b-0 md:border-r">
      <div className="px-5 py-5">
        <p className="text-lg font-semibold text-slate-900">My API Integration Assistant</p>
        <p className="text-xs text-slate-500">Requirements → tested API integrations</p>
      </div>
      {/* The highlighted item depends on the URL, so it loads inside Suspense.
          Until then, the same menu shows without a highlight. */}
      <Suspense fallback={<NavLinks activeHref={null} />}>
        <ActiveNavLinks />
      </Suspense>
    </aside>
  );
}
