import type { CaseEnvelope } from "@/lib/contracts";
import clsx from "clsx";

type Observables = CaseEnvelope["observables"];
type ObsKind = keyof Observables;

const groups: Record<ObsKind, "net" | "host" | "hash" | "id"> = {
  ipv4: "net",
  url: "net",
  domain: "net",
  email: "net",
  hostname: "host",
  process: "host",
  filename: "host",
  registry_path: "host",
  md5: "hash",
  sha1: "hash",
  sha256: "hash",
  username: "id",
};

const groupClass = {
  net: "bg-obs-net text-obs-net-fg",
  host: "bg-obs-host text-obs-host-fg",
  hash: "bg-obs-hash text-obs-hash-fg",
  id: "bg-obs-id text-obs-id-fg",
};

const order: ObsKind[] = [
  "ipv4", "url", "domain", "email", "hostname", "process",
  "filename", "registry_path", "md5", "sha1", "sha256", "username",
];

export function ObservablesPanel({ observables }: { observables: Observables }) {
  const pills: { kind: string; value: string; cls: string }[] = [];
  for (const kind of order) {
    for (const value of observables[kind] ?? []) {
      pills.push({
        kind: String(kind),
        value,
        cls: groupClass[groups[kind]],
      });
    }
  }
  if (pills.length === 0) {
    return <p className="text-ink-faint text-sm">No observables extracted.</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {pills.map((p, i) => (
        <span
          key={`${p.kind}-${p.value}-${i}`}
          title={p.kind}
          className={clsx(
            "inline-block px-2 py-0.5 rounded text-[0.7rem] font-medium font-mono",
            p.cls,
          )}
        >
          {p.value}
        </span>
      ))}
    </div>
  );
}
