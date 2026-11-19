"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "@/lib/navigation";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-slate-200 bg-white md:h-screen md:w-64 md:border-b-0 md:border-r">
      <div className="px-5 py-5">
        <p className="text-lg font-semibold text-slate-900">My API Integration Assistant</p>
        <p className="text-xs text-slate-500">Requirements → tested API integrations</p>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`whitespace-nowrap rounded-md px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-indigo-50 font-medium text-indigo-700"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
