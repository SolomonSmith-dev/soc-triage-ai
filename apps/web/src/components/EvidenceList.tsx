import type { CaseEnvelope } from "@/lib/contracts";

type Evidence = CaseEnvelope["evidence"];

export function EvidenceList({ evidence }: { evidence: Evidence }) {
  if (evidence.chunks_retrieved.length === 0) {
    return <p className="text-ink-faint text-sm">No retrieved chunks.</p>;
  }
  return (
    <ul className="space-y-3">
      {evidence.chunks_retrieved.map((c, i) => (
        <li key={`${c.chunk_id}-${i}`} className="card p-4">
          <div className="flex items-baseline gap-3 text-xs text-ink-dim mb-2">
            <span className="font-mono text-ink">{c.chunk_id}</span>
            <span className="font-mono">{c.source}</span>
            <span>score {c.score.toFixed(3)}</span>
            {c.cited ? (
              <span className="text-emerald-400 font-bold">cited</span>
            ) : (
              <span className="text-ink-faint">not cited</span>
            )}
          </div>
          <pre className="text-xs text-ink-dim whitespace-pre-wrap font-mono">
            {c.text.slice(0, 600)}
          </pre>
        </li>
      ))}
    </ul>
  );
}
