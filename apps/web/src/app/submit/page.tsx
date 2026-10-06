import { SubmitForm } from "./SubmitForm";

export default function SubmitPage() {
  return (
    <section className="space-y-4 max-w-3xl">
      <div>
        <h2 className="text-base font-semibold">Submit an alert</h2>
        <p className="text-xs text-ink-mute">
          Paste raw alert text from your SIEM or EDR. Triage runs synchronously
          (~8s). The case page opens automatically when complete.
        </p>
      </div>
      <SubmitForm />
    </section>
  );
}
