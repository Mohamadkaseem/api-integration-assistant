"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { MermaidDiagram } from "@/components/MermaidDiagram";
import { downloadFile, getAIStatus, getHandover, improveHandoverAI, listProjects, type AIStatus, type HandoverData, type Project } from "@/lib/api";
import { mermaidToPngBase64 } from "@/lib/diagramImage";

function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="mt-8 border-b border-slate-200 pb-1 text-lg font-semibold text-slate-900">{children}</h2>;
}

function Table({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 text-slate-500">
          <tr>{headers.map((h) => <th key={h} className="px-2 py-1.5 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {rows.map((row, i) => (
            <tr key={i} className="align-top">{row.map((c, j) => <td key={j} className="px-2 py-1.5">{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Bullets({ items, empty = "None." }: { items: string[]; empty?: string }) {
  if (!items.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>;
}

function Code({ text }: { text: string }) {
  if (!text) return null;
  let shown = text.replace(/^\[[^\]]+\]\n/, "");
  try {
    if (/^\s*[[{]/.test(shown)) shown = JSON.stringify(JSON.parse(shown), null, 2);
  } catch {
    /* keep as is */
  }
  return <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{shown}</pre>;
}

const TRUST: Record<string, string> = { spec: "verified (from spec)", quoted: "quoted from document", unverified: "⚠ UNVERIFIED" };

export function HandoverDocs() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = Number(searchParams.get("project")) || null;
  const [projects, setProjects] = useState<Project[]>([]);
  const [data, setData] = useState<HandoverData | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]));
    getAIStatus().then(setAIStatus).catch(() => setAIStatus(null));
  }, []);

  useEffect(() => {
    if (!projectId) return;
    getHandover(projectId)
      .then((r) => {
        setData(r.data);
        setMarkdown(r.markdown);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [projectId]);

  async function act(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed.");
    } finally {
      setBusy(null);
    }
  }

  const downloadWord = () =>
    act("word", async () => {
      const picture = data && data.steps.length ? await mermaidToPngBase64(data.mermaid) : null;
      await downloadFile(
        `/api/projects/${projectId}/handover/docx`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ diagram_png_base64: picture }) },
        "handover.docx",
      );
    });
  const downloadMarkdown = () => act("md", () => downloadFile(`/api/projects/${projectId}/handover/markdown`, {}, "handover.md"));
  const improve = () =>
    act("ai", async () => {
      const r = await improveHandoverAI(projectId!);
      setData(r.data);
      setMarkdown(r.markdown);
    });

  const button = "rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Handover Docs</h1>
          <p className="mt-1 text-slate-600">Everything about a project in one developer document — preview, then export to Word or Markdown.</p>
        </div>
        <select className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm" value={projectId ?? ""} onChange={(e) => router.push(`?project=${e.target.value}`)}>
          <option value="">Choose a project…</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      {!projectId && <p className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">Choose a project to generate its handover document.</p>}
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      {projectId && data && (
        <>
          <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white/95 p-3 backdrop-blur">
            <button onClick={downloadWord} disabled={busy !== null} className={`${button} bg-indigo-600 text-white hover:bg-indigo-700`}>
              {busy === "word" ? "Preparing Word…" : "Download Word (.docx)"}
            </button>
            <button onClick={downloadMarkdown} disabled={busy !== null} className={`${button} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`}>
              Download Markdown
            </button>
            <button
              onClick={async () => {
                await navigator.clipboard.writeText(markdown);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className={`${button} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`}
            >
              {copied ? "Copied ✓" : "Copy Markdown"}
            </button>
            <button
              onClick={improve}
              disabled={busy !== null || (aiStatus !== null && !aiStatus.configured)}
              title={aiStatus && !aiStatus.configured ? "Needs your Claude API key" : ""}
              className={`${button} ml-auto border border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-50`}
            >
              {busy === "ai" ? "Claude is writing…" : data.ai_summary ? "Rewrite summary with AI" : "Improve with AI (summary + extra tests)"}
            </button>
          </div>

          <article className="rounded-lg border border-slate-200 bg-white p-6 sm:p-8">
            <h1 className="text-2xl font-bold text-slate-900">{data.project_name}</h1>
            <p className="mt-1 text-sm text-slate-500">
              Developer handover · Source: {data.source_app || "—"} · Target: {data.target_app || "—"} · Status: {data.status} · Generated {data.generated_at}
            </p>

            <H2>1. Overview</H2>
            {data.ai_summary && <p className="mt-2 rounded-md bg-indigo-50/60 p-3 text-sm text-slate-800">{data.ai_summary}</p>}
            {data.summary && <p className="mt-2 text-sm text-slate-700"><b>Use case:</b> {data.summary}</p>}
            <p className="mt-2 text-sm font-medium text-slate-700">Business requirement (as given):</p>
            <blockquote className="mt-1 border-l-4 border-indigo-200 pl-3 text-sm italic text-slate-700">{data.requirement || "Not written yet."}</blockquote>
            {data.expected_outcome && <p className="mt-2 text-sm text-slate-700"><b>Expected outcome:</b> {data.expected_outcome}</p>}

            <H2>2. Trigger &amp; workflow</H2>
            <p className="mt-2 text-sm text-slate-700"><b>Trigger:</b> {data.trigger || "Not defined."}</p>
            {data.steps.length > 0 ? (
              <>
                <div className="mt-3"><MermaidDiagram text={data.mermaid} /></div>
                <Table
                  headers={["#", "App", "Action", "Description", "Only when", "Waits for", "Endpoint"]}
                  rows={data.steps.map((s) => [s.order, s.app, s.action, s.description, s.condition, s.waits_for, s.endpoint_label || (s.match_status === "no_endpoint" ? "⚠ none documented" : "—")])}
                />
              </>
            ) : (
              <p className="mt-2 text-sm text-slate-500">No steps designed yet — add them under Integration design.</p>
            )}
            {data.conditions.length > 0 && <><p className="mt-3 text-sm font-medium">Conditions &amp; business rules</p><Bullets items={data.conditions} /></>}
            {data.status_updates.length > 0 && <><p className="mt-3 text-sm font-medium">Status updates</p><Bullets items={data.status_updates} /></>}

            <H2>3. API endpoints</H2>
            {data.endpoints.length === 0 && <p className="mt-2 text-sm text-slate-500">No endpoints chosen yet.</p>}
            {data.endpoints.map((e, i) => (
              <section key={i} className="mt-4">
                <h3 className="font-mono text-sm font-semibold text-slate-900">3.{i + 1} {e.method} {e.path}</h3>
                <p className="text-xs text-slate-600">
                  {e.app} · step(s) {e.step_orders.join(", ")} · {TRUST[e.verification] ?? e.verification}
                </p>
                <p className="break-all font-mono text-xs text-slate-700">{e.full_url}</p>
                {e.summary && <p className="text-sm text-slate-700">{e.summary}</p>}
                {e.parameters.length > 0 && (
                  <Table headers={["Parameter", "In", "Type", "Required", "Description"]} rows={e.parameters.map((p) => [p.name, p.location, p.type, p.required ? "yes" : "", p.description])} />
                )}
                {e.request_body && <><p className="mt-2 text-xs font-semibold">Request body</p><Code text={e.request_body} /></>}
                {e.responses.map((r, j) => (
                  <div key={j}><p className="mt-2 text-xs font-semibold">Response {r.status} {r.description}</p><Code text={r.example} /></div>
                ))}
              </section>
            ))}

            <H2>4. Authentication</H2>
            <p className="mt-1 text-xs text-slate-500">Secrets are never included in this document.</p>
            {data.authentication.length ? (
              <Table headers={["App", "Source", "Details"]} rows={data.authentication.map((a) => [a.app, a.source, a.description])} />
            ) : (
              <p className="mt-2 text-sm text-slate-500">No authentication information recorded.</p>
            )}

            <H2>5. Field mapping</H2>
            {data.mappings.length ? (
              <Table
                headers={["Source", "Source field", "Target", "Target field", "Transformation", "Req.", "Issue", "Evidence"]}
                rows={data.mappings.map((m) => [m.source_app, m.source_field, m.target_app, m.target_field, m.transform, m.required ? "yes" : "", m.issue, m.evidence])}
              />
            ) : data.data_to_transfer.length ? (
              <Table headers={["Data", "From", "To", "Notes"]} rows={data.data_to_transfer.map((x) => [x.name, x.from_app, x.to_app, x.notes])} />
            ) : (
              <p className="mt-2 text-sm text-slate-500">No mappings yet.</p>
            )}

            <H2>6. Error handling</H2>
            <Table headers={["Error", "Meaning", "Handling"]} rows={data.errors.map((e) => [e.code, e.meaning, e.handling])} />

            <H2>7. Test cases</H2>
            {data.test_cases.length ? (
              <Table
                headers={["ID", "Test", "Preconditions", "Steps", "Expected result"]}
                rows={data.test_cases.map((t) => [t.id + (t.source === "ai" ? " (AI)" : ""), t.title, t.preconditions, t.steps, t.expected])}
              />
            ) : (
              <p className="mt-2 text-sm text-slate-500">Add workflow steps to generate test cases.</p>
            )}

            {data.samples.length > 0 && (
              <>
                <H2>8. Sample requests (from testing)</H2>
                <p className="mt-1 text-xs text-slate-500">Captured in the Request Builder; secrets were masked when saved.</p>
                {data.samples.map((s, i) => (
                  <div key={i} className="mt-3">
                    <p className="font-mono text-xs"><b>{s.method}</b> {s.url} → <b>{s.status}</b> ({s.when})</p>
                    <Code text={s.request_body} />
                    <Code text={s.response_body} />
                  </div>
                ))}
              </>
            )}

            <H2>9. Assumptions &amp; open points</H2>
            <p className="mt-2 text-sm font-medium">Assumptions</p>
            <Bullets items={data.assumptions} />
            <p className="mt-3 text-sm font-medium">Open points</p>
            <Bullets items={data.open_points} empty="No open points." />
          </article>
        </>
      )}
    </div>
  );
}
