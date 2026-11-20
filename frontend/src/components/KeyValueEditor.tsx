"use client";

import type { KeyValue } from "@/lib/api";
import { MASK } from "@/lib/requests";

type Props = { rows: KeyValue[]; onChange: (rows: KeyValue[]) => void; namePlaceholder: string };

const cell = "w-full rounded border border-slate-300 px-2 py-1.5 font-mono text-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-200";

export function KeyValueEditor({ rows, onChange, namePlaceholder }: Props) {
  const update = (i: number, patch: Partial<KeyValue>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <input type="checkbox" checked={row.enabled} onChange={(e) => update(i, { enabled: e.target.checked })} title="Include" />
          <input className={cell} placeholder={namePlaceholder} value={row.name} onChange={(e) => update(i, { name: e.target.value })} />
          <input
            className={`${cell} ${row.value === MASK ? "bg-amber-50" : ""}`}
            placeholder={row.value === MASK ? "secret not saved - enter again" : "value"}
            value={row.value === MASK ? "" : row.value}
            onChange={(e) => update(i, { value: e.target.value })}
          />
          <button type="button" onClick={() => onChange(rows.filter((_, j) => j !== i))} className="px-1 text-slate-400 hover:text-rose-600" title="Remove">
            ✕
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...rows, { name: "", value: "", enabled: true }])} className="text-xs font-medium text-indigo-700 hover:underline">
        + Add
      </button>
    </div>
  );
}
