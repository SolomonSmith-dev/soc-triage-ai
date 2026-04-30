import Link from "next/link";
import { notFound } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { SeverityBadge } from "@/components/SeverityBadge";
import { UncertaintyBadge } from "@/components/UncertaintyBadge";
import { MitreChip } from "@/components/MitreChip";
import { SourcePill } from "@/components/SourcePill";
import { ObservablesPanel } from "@/components/ObservablesPanel";
import { EvidenceList } from "@/components/EvidenceList";
import { MetricCard } from "@/components/MetricCard";

export const dynamic = "force-dynamic";

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let envelope;
  try {
    envelope = await api.getCase(id);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  const t = envelope.triage;

  return (
    <article className="space-y-6">
      <header className="flex items-start justify-between">
        <div>
          <p className="text-xs text-ink-mute mb-1">Case</p>
          <h2 className="font-mono text-lg text-ink">{envelope.case_id}</h2>
          <p className="text-xs text-ink-mute mt-1">
            {new Date(envelope.timestamp).toLocaleString()}
          </p>
        </div>
        <Link href="/" className="text-xs text-ink-mute hover:text-ink underline">
          ← back to dashboard
        </Link>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Severity">
          <SeverityBadge severity={t.severity} />
        </MetricCard>
        <MetricCard label="Escalate">
          {t.escalate ? (
            <span className="text-red-400 font-bold">YES — escalate</span>
          ) : (
            <span className="text-ink-faint">NO</span>
          )}
        </MetricCard>
        <MetricCard label="Confidence">
          <span className="uppercase">{t.confidence}</span>
        </MetricCard>
        <MetricCard label="Uncertainty">
          <UncertaintyBadge mode={envelope.uncertainty_mode} />
        </MetricCard>
      </div>

      <section className="space-y-2">
        <div className="sec-label">Alert</div>
        <div className="card p-4">
          <pre className="font-mono text-sm whitespace-pre-wrap text-ink-dim">
            {envelope.alert_raw}
          </pre>
        </div>
      </section>

      <section className="space-y-2">
        <div className="sec-label">Observables</div>
        <div className="card p-4">
          <ObservablesPanel observables={envelope.observables} />
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 space-y-2">
          <div className="sec-label">Summary</div>
          <div className="card p-4 text-sm text-ink-dim">{t.summary}</div>
          <div className="sec-label mt-4">Recommended actions</div>
          <ol className="card p-4 list-decimal pl-6 text-sm text-ink-dim space-y-1">
            {t.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
          </ol>
          <div className="sec-label mt-4">Reasoning</div>
          <div className="card p-4 border-l-4 border-l-blue-600 text-sm text-ink-dim leading-relaxed">
            {t.reasoning}
          </div>
        </div>

        <aside className="space-y-3">
          <div>
            <div className="sec-label mb-2">MITRE ATT&amp;CK</div>
            <div>
              {t.mitre_techniques.length === 0 ? (
                <span className="text-ink-faint text-sm">None identified</span>
              ) : (
                t.mitre_techniques.map((m) => <MitreChip key={m} technique={m} />)
              )}
            </div>
          </div>
          <div>
            <div className="sec-label mb-2">Sources cited</div>
            <div>
              {envelope.evidence.sources_cited.length === 0 ? (
                <span className="text-ink-faint text-sm">N/A</span>
              ) : (
                envelope.evidence.sources_cited.map((s) => <SourcePill key={s} source={s} />)
              )}
            </div>
          </div>
          <div className="card p-3">
            <div className="sec-label mb-1">Avg retrieval</div>
            <div className="font-mono text-base text-ink">
              {envelope.evidence.avg_retrieval_score.toFixed(3)}
            </div>
          </div>
        </aside>
      </section>

      <section className="space-y-2">
        <div className="sec-label">Evidence — retrieved chunks</div>
        <EvidenceList evidence={envelope.evidence} />
      </section>
    </article>
  );
}
