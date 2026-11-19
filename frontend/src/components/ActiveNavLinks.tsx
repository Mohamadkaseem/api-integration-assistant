"use client";

import { usePathname } from "next/navigation";

import { NavLinks } from "@/components/NavLinks";
import { NAV_ITEMS } from "@/lib/navigation";

// Works out which menu item matches the current page, e.g. /projects/3 → "Projects".
export function ActiveNavLinks() {
  const pathname = usePathname();
  const active = NAV_ITEMS.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );
  return <NavLinks activeHref={active?.href ?? null} />;
}
