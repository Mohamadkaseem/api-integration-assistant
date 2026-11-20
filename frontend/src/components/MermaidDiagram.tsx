"use client";

import { useEffect, useRef, useState } from "react";

// Renders Mermaid text (e.g. "flowchart TD ...") as an SVG diagram.
export function MermaidDiagram({ text }: { text: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral", htmlLabels: true, flowchart: { htmlLabels: true } });
        const { svg } = await mermaid.render(`diagram-${Date.now()}`, text);
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg; // Mermaid's own sanitised output (securityLevel: strict)
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not draw the diagram.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [text]);

  return (
    <div>
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      <div ref={ref} className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-4 [&_svg]:mx-auto [&_svg]:max-w-full" />
    </div>
  );
}
