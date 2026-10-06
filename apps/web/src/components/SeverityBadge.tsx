import clsx from "clsx";

const styles: Record<string, string> = {
  critical: "bg-sev-critical text-sev-critical-fg",
  high: "bg-sev-high text-sev-high-fg",
  medium: "bg-sev-medium text-sev-medium-fg",
  low: "bg-sev-low text-sev-low-fg",
  informational: "bg-sev-informational text-sev-informational-fg",
};

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = styles[severity] ?? styles.informational;
  return (
    <span
      className={clsx(
        "inline-block px-2.5 py-1 rounded text-[0.7rem] font-bold uppercase tracking-wide",
        cls,
      )}
    >
      {severity}
    </span>
  );
}
