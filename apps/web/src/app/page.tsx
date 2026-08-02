import Link from "next/link";
import { api } from "@/lib/api";
import { SeverityBadge } from "@/components/SeverityBadge";
import { UncertaintyBadge } from "@/components/UncertaintyBadge";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const cases = await api.listCases(50);

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">Recent cases</h2>
          <p className="text-xs text-ink-mute">
            {cases.length} case{cases.length === 1 ? "" : "s"} · most recent first
          </p>
        </div>
        <Link
          href="/submit"
          className="text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium px-3 py-1.5 rounded"
        >
          Submit alert
        </Link>
      </div>

      {cases.length === 0 ? (
        <div className="card p-8 text-center text-ink-mute text-sm">
          No cases yet. <Link href="/submit" className="text-blue-400 underline">Submit an alert</Link> to get started.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-bg-elev border-b border-border">
              <tr className="text-left text-xs text-ink-mute uppercase tracking-wide">
                <th className="px-4 py-2 font-semibold">Case</th>
                <th className="px-4 py-2 font-semibold">Severity</th>
                <th className="px-4 py-2 font-semibold">Escalate</th>
                <th className="px-4 py-2 font-semibold">Mode</th>
                <th className="px-4 py-2 font-semibold">Score</th>
                <th className="px-4 py-2 font-semibold">Summary</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr
                  key={c.case_id}
                  className="border-b border-border last:border-b-0 hover:bg-bg-elev"
                >
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link href={`/cases/${c.case_id}`} className="text-blue-400 hover:underline">
                      {c.case_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={c.severity} />
                  </td>
                  <td className="px-4 py-3 text-ink-dim">{c.escalate ? "yes" : "no"}</td>
                  <td className="px-4 py-3">
                    <UncertaintyBadge mode={c.uncertainty_mode} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-dim">
                    {c.retrieval_score?.toFixed(3) ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-ink-dim text-xs truncate max-w-md">
                    {c.summary}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
