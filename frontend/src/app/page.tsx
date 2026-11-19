import { BackendStatus } from "@/components/BackendStatus";

// Real numbers arrive with the database (M2) and API testing (M4).
const STATS = [
  { label: "Integration projects", value: "0" },
  { label: "Saved API requests", value: "0" },
  { label: "Successful test calls", value: "0" },
  { label: "Failed test calls", value: "0" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-slate-600">Overview of your integration projects.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((stat) => (
          <div key={stat.label} className="rounded-lg border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-500">{stat.label}</p>
            <p className="mt-2 text-3xl font-semibold text-slate-900">{stat.value}</p>
          </div>
        ))}
      </div>

      <BackendStatus />
    </div>
  );
}
