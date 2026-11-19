import type { NavItem } from "@/lib/navigation";

export function ComingSoon({ item }: { item: NavItem }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">{item.label}</h1>
      <p className="mt-1 text-slate-600">{item.description}</p>
      <div className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-sm text-slate-500">
          This section is planned for <span className="font-medium text-slate-700">{item.milestone}</span>.
        </p>
      </div>
    </div>
  );
}
