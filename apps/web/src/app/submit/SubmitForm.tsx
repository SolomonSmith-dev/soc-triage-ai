"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const SAMPLES: Record<string, string> = {
  "Active ransomware":
    "Multiple file servers showing thousands of file modifications per minute. " +
    "Files renamed with .lockbit extension. README.txt ransom notes appearing in " +
    "every directory. Volume Shadow Copies deleted via vssadmin 30 minutes ago.",
  "LSASS credential dump":
    "EDR detected suspicious access to LSASS process memory by rundll32.exe with " +
    "comsvcs.dll on workstation WKSTN-042. User account is jsmith. " +
    "Process tree: cmd.exe -> rundll32.exe.",
  "Phishing + credential entry":
    "User reported email from ceo@anthrop1c.com (note typo) requesting urgent " +
    "wire transfer to new vendor. User clicked link and entered credentials " +
    "before reporting. Email contained urgency language.",
  "Insider data exfiltration":
    "Employee jdoe (resignation notice given last week) downloaded 15GB of " +
    "customer data from CRM in last 24 hours. Login from new device fingerprint. " +
    "Email forwarding rule created to personal Gmail yesterday.",
};

export function SubmitForm() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setErr(null);
    setBusy(true);
    try {
      const ingest = await api.ingestAlert({ raw_text: text, source: "manual" });
      const job = await api.submitTriage({ alert_id: ingest.alert_id });
      if (job.case_id) {
        router.push(`/cases/${job.case_id}`);
      } else {
        setErr("Triage completed without a case_id. Check API logs.");
        setBusy(false);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Submission failed.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="card p-4">
        <div className="sec-label mb-2">Sample alerts</div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(SAMPLES).map(([label, body]) => (
            <button
              key={label}
              type="button"
              onClick={() => setText(body)}
              className="text-xs bg-bg-elev border border-border hover:border-ink-mute text-ink-dim px-2.5 py-1 rounded"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste raw alert text..."
        rows={10}
        className="w-full card p-3 font-mono text-sm bg-bg-card text-ink placeholder-ink-faint resize-y"
      />

      {err && (
        <div className="card p-3 border-red-900 text-red-400 text-sm">
          {err}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-bg-elev disabled:text-ink-faint text-white font-medium px-4 py-2 rounded text-sm"
        >
          {busy ? "Triaging… (~8s)" : "Run triage"}
        </button>
        <span className="text-xs text-ink-mute">
          Synchronous mode. Phase 3 swaps to async background workers.
        </span>
      </div>
    </form>
  );
}
