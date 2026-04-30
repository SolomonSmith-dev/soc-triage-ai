export function MetricCard({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card px-4 py-3">
      <div className="sec-label mb-1">{label}</div>
      <div className="text-base font-semibold text-ink">{children}</div>
    </div>
  );
}
