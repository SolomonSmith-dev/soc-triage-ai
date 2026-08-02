import clsx from "clsx";

const styles: Record<string, string> = {
  actionable: "bg-sev-low text-sev-low-fg",
  needs_more_context: "bg-sev-medium text-sev-medium-fg",
  insufficient_evidence: "bg-sev-high text-sev-high-fg",
  out_of_scope: "bg-sev-informational text-sev-informational-fg",
};

export function UncertaintyBadge({ mode }: { mode: string }) {
  const cls = styles[mode] ?? styles.actionable;
  return (
    <span
      className={clsx(
        "inline-block px-2.5 py-1 rounded text-[0.65rem] font-semibold uppercase tracking-wide",
        cls,
      )}
    >
      {mode.replace(/_/g, " ")}
    </span>
  );
}
