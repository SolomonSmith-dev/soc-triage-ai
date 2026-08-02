import { api, ApiError } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";

export const dynamic = "force-dynamic";

export default async function EvalPage() {
  let summary;
  try {
    summary = await api.latestEval();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      return (
        <div className="card p-6">
          <h2 className="text-base font-semibold mb-2">No harness results</h2>
          <p className="text-sm text-ink-dim">
            Run <code className="font-mono">python -m tests.harness.test_harness</code> to populate.
          </p>
        </div>
      );
    }
    throw e;
  }

  const m = summary.metrics;

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-base font-semibold">Reliability harness</h2>
        <p className="text-xs text-ink-mute">7 canonical alerts, regression-tested.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard label="Pass rate">
          {Math.round(m.pass_rate * 100)}% ({m.passed}/{m.total})
        </MetricCard>
        <MetricCard label="Severity">
          {m.severity_accuracy != null
            ? `${Math.round(m.severity_accuracy * 100)}%`
            : "n/a"}
        </MetricCard>
        <MetricCard label="Escalation">
          {m.escalation_accuracy != null
            ? `${Math.round(m.escalation_accuracy * 100)}%`
            : "n/a"}
        </MetricCard>
        <MetricCard label="Avg retrieval">
          {m.avg_retrieval_score.toFixed(3)}
        </MetricCard>
        <MetricCard label="Avg latency">{m.avg_latency.toFixed(1)}s</MetricCard>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-bg-elev border-b border-border">
            <tr className="text-left text-xs text-ink-mute uppercase tracking-wide">
              <th className="px-4 py-2 font-semibold">Test</th>
              <th className="px-4 py-2 font-semibold">Severity</th>
              <th className="px-4 py-2 font-semibold">Escalate</th>
              <th className="px-4 py-2 font-semibold">Techniques</th>
              <th className="px-4 py-2 font-semibold">Score</th>
              <th className="px-4 py-2 font-semibold">Latency</th>
              <th className="px-4 py-2 font-semibold">Result</th>
            </tr>
          </thead>
          <tbody>
            {m.per_case.map((r) => (
              <tr key={r.id} className="border-b border-border last:border-b-0">
                <td className="px-4 py-3 font-mono text-xs">{r.id}</td>
                <td className="px-4 py-3">{r.severity ?? "—"}</td>
                <td className="px-4 py-3 text-ink-dim">
                  {r.escalate == null ? "—" : r.escalate ? "yes" : "no"}
                </td>
                <td className="px-4 py-3 text-ink-dim text-xs">
                  {(r.techniques ?? []).join(", ")}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {r.retrieval_score?.toFixed(3) ?? "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {r.latency_seconds?.toFixed(1) ?? "—"}s
                </td>
                <td className="px-4 py-3">
                  {r.passed ? (
                    <span className="text-emerald-400 font-bold text-xs">PASS</span>
                  ) : (
                    <span className="text-red-400 font-bold text-xs">FAIL</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
