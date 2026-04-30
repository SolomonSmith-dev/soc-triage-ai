export function SourcePill({ source }: { source: string }) {
  return (
    <span className="inline-block bg-bg-card border border-border text-ink-dim font-mono text-[0.7rem] px-1.5 py-0.5 rounded mr-1.5 mb-1.5">
      {source}
    </span>
  );
}
