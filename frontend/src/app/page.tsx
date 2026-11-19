import Link from "next/link";

import { BackendStatus } from "@/components/BackendStatus";
import { ProjectCount } from "@/components/ProjectCount";

// "Saved API requests" and the test-call counts become real in M4 (Request Builder).
const STATS = [
  { label: "Integration projects", value: <ProjectCount />, href: "/projects" },
  { label: "Saved API requests", value: "0", href: null },
  { label: "Successful test calls", value: "0", href: null },
  { label: "Failed test calls", value: "0", href: null },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-slate-600">Overview of your integration projects.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((stat) => {
          const card = (
            <div className="h-full rounded-lg border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">{stat.label}</p>
              <p className="mt-2 text-3xl font-semibold text-slate-900">{stat.value}</p>
            </div>
          );
          return stat.href ? (
            <Link key={stat.label} href={stat.href} className="transition hover:opacity-80">
              {card}
            </Link>
          ) : (
            <div key={stat.label}>{card}</div>
          );
        })}
      </div>

      <BackendStatus />
    </div>
  );
}
