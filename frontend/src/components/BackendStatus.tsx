"use client";

import { useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "online"; data: HealthResponse }
  | { kind: "offline"; error: string };

export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    getHealth()
      .then((data) => setState({ kind: "online", data }))
      .catch((error: Error) => setState({ kind: "offline", error: error.message }));
  }, []);

  const dot =
    state.kind === "online" ? "bg-emerald-500" : state.kind === "offline" ? "bg-rose-500" : "bg-amber-400";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <h2 className="text-sm font-semibold text-slate-900">Backend status</h2>
      </div>
      {state.kind === "loading" && <p className="mt-2 text-sm text-slate-500">Checking connection…</p>}
      {state.kind === "online" && (
        <p className="mt-2 text-sm text-slate-600">
          Connected to <span className="font-medium">{state.data.app_name}</span> v{state.data.version} (
          {state.data.environment})
        </p>
      )}
      {state.kind === "offline" && (
        <p className="mt-2 text-sm text-rose-600">
          Cannot reach the backend. Is it running on port 8000? ({state.error})
        </p>
      )}
    </div>
  );
}
