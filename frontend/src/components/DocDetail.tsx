"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { VerificationBadge } from "@/components/VerificationBadge";
import { deleteDoc, deleteEndpoint, getDoc, type ApiDocDetail, type ApiEndpoint, type Verification } from "@/lib/api";
import { METHOD_STYLE, SOURCE_LABEL, VERIFICATION } from "@/lib/docs";

const PAGE_SIZE = 100;

function EndpointRow({ endpoint, onDelete }: { endpoint: ApiEndpoint; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-lg border border-slate-200 bg-white">
      <button onClick={() => setOpen(!open)} className="flex w-full items-start gap-3 p-3 text-left">
        <span className={`mt-0.5 w-16 shrink-0 rounded px-1.5 py-0.5 text-center text-xs font-bold text-white ${METHOD_STYLE[endpoint.method] ?? "bg-slate-500"}`}>
          {endpoint.method}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block break-all font-mono text-sm text-slate-900">{endpoint.path}</span>
          {endpoint.summary && <span className="block text-sm text-slate-600">{endpoint.summary}</span>}
        </span>
        <VerificationBadge value={endpoint.verification} />
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-100 p-4 text-sm">
          {endpoint.verification !== "spec" && endpoint.evidence && (
            <div className={`rounded-md p-3 ${endpoint.verification === "unverified" ? "bg-amber-50" : "bg-sky-50"}`}>
              <p className="text-xs font-semibold text-slate-700">Quote from the document</p>
              <p className="mt-1 font-mono text-xs text-slate-800">“{endpoint.evidence}”</p>
              <p className="mt-1 text-xs text-slate-600">{VERIFICATION[endpoint.verification].help}</p>
            </div>
          )}
          {endpoint.description && <p className="whitespace-pre-wrap text-slate-700">{endpoint.description}</p>}
          {endpoint.auth && (
            <p className="text-slate-700">
              <span className="font-medium">Authentication:</span> {endpoint.auth}
            </p>
          )}
          {endpoint.parameters.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 pr-3 font-medium">Parameter</th>
                    <th className="py-1 pr-3 font-medium">In</th>
                    <th className="py-1 pr-3 font-medium">Type</th>
                    <th className="py-1 pr-3 font-medium">Required</th>
                    <th className="py-1 font-medium">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {endpoint.parameters.map((p, i) => (
                    <tr key={i}>
                      <td className="py-1 pr-3 font-mono">{p.name}</td>
                      <td className="py-1 pr-3">{p.location}</td>
                      <td className="py-1 pr-3">{p.type}</td>
                      <td className="py-1 pr-3">{p.required ? "yes" : ""}</td>
                      <td className="py-1">{p.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {endpoint.request_body && (
            <div>
              <p className="text-xs font-semibold text-slate-700">Request body</p>
              <pre className="mt-1 max-h-80 overflow-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">{endpoint.request_body}</pre>
            </div>
          )}
          {endpoint.responses.map((r, i) => (
            <div key={i}>
              <p className="text-xs font-semibold text-slate-700">
                Response {r.status} {r.description && <span className="font-normal text-slate-500">— {r.description}</span>}
              </p>
              {r.example && <pre className="mt-1 max-h-60 overflow-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">{r.example}</pre>}
            </div>
          ))}
          <button onClick={onDelete} className="text-xs font-medium text-rose-700 hover:underline">
            Remove this endpoint
          </button>
        </div>
      )}
    </li>
  );
}

export function DocDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const docId = Number(params.id);
  const [doc, setDoc] = useState<ApiDocDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [method, setMethod] = useState("");
  const [level, setLevel] = useState<"" | Verification>("");
  const [limit, setLimit] = useState(PAGE_SIZE);

  useEffect(() => {
    getDoc(docId)
      .then(setDoc)
      .catch((err: Error) => setError(err.message));
  }, [docId]);

  const filtered = useMemo(() => {
    if (!doc) return [];
    const q = search.trim().toLowerCase();
    return doc.endpoints.filter(
      (e) =>
        (!method || e.method === method) &&
        (!level || e.verification === level) &&
        (!q || `${e.path} ${e.summary} ${e.description}`.toLowerCase().includes(q)),
    );
  }, [doc, search, method, level]);

  async function removeEndpoint(endpoint: ApiEndpoint) {
    if (!doc || !window.confirm(`Remove ${endpoint.method} ${endpoint.path} from this document?`)) return;
    try {
      await deleteEndpoint(doc.id, endpoint.id);
      setDoc({ ...doc, endpoints: doc.endpoints.filter((e) => e.id !== endpoint.id), endpoint_count: doc.endpoint_count - 1 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove the endpoint.");
    }
  }

  async function removeDoc() {
    if (!doc || !window.confirm(`Delete "${doc.app_name}" documentation and all ${doc.endpoint_count} endpoints?`)) return;
    try {
      await deleteDoc(doc.id);
      router.push("/api-docs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the document.");
    }
  }

  const methods = doc ? Array.from(new Set(doc.endpoints.map((e) => e.method))) : [];
  const selectClass = "rounded-md border border-slate-300 bg-white px-2 py-2 text-sm";

  return (
    <div className="space-y-6">
      <Link href="/api-docs" className="text-sm text-indigo-700 hover:underline">
        ← All documentation
      </Link>
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {!doc && !error && <p className="text-sm text-slate-500">Loading…</p>}

      {doc && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold text-slate-900">{doc.app_name}</h1>
              <p className="text-slate-600">
                {doc.title} {doc.version && <span className="text-slate-400">v{doc.version}</span>}
              </p>
              <p className="mt-1 break-all text-xs text-slate-500">
                {SOURCE_LABEL[doc.source_type]} · {doc.source_ref}
              </p>
            </div>
            <button onClick={removeDoc} className="rounded-md border border-rose-300 bg-white px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50">
              Delete
            </button>
          </div>

          {doc.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <ul className="list-disc space-y-1 pl-5">
                {doc.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">Base URLs</h2>
              {doc.base_urls.length ? (
                <ul className="mt-2 space-y-1 break-all font-mono text-xs text-slate-700">
                  {doc.base_urls.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-500">Not stated in the document.</p>
              )}
            </section>
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">Authentication</h2>
              {doc.auth_schemes.length ? (
                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                  {doc.auth_schemes.map((a) => (
                    <li key={a.name}>
                      <span className="font-medium">{a.name}</span> <span className="text-slate-500">({a.type})</span>
                      {a.details && <p className="break-all text-xs text-slate-600">{a.details}</p>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-500">Not stated in the document.</p>
              )}
            </section>
          </div>

          <section className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setLimit(PAGE_SIZE);
                }}
                placeholder={`Search ${doc.endpoint_count} endpoints…`}
                className="min-w-48 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
              <select value={method} onChange={(e) => setMethod(e.target.value)} className={selectClass}>
                <option value="">All methods</option>
                {methods.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
              <select value={level} onChange={(e) => setLevel(e.target.value as "" | Verification)} className={selectClass}>
                <option value="">All trust levels</option>
                {(["spec", "quoted", "unverified"] as const).map((v) => (
                  <option key={v} value={v}>
                    {VERIFICATION[v].label} ({doc.counts[v] ?? 0})
                  </option>
                ))}
              </select>
            </div>
            <p className="text-xs text-slate-500">
              Showing {Math.min(limit, filtered.length)} of {filtered.length}. Click an endpoint for details.
            </p>
            <ul className="space-y-2">
              {filtered.slice(0, limit).map((e) => (
                <EndpointRow key={e.id} endpoint={e} onDelete={() => removeEndpoint(e)} />
              ))}
            </ul>
            {filtered.length > limit && (
              <button onClick={() => setLimit(limit + PAGE_SIZE)} className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
                Show more
              </button>
            )}
          </section>
        </>
      )}
    </div>
  );
}
