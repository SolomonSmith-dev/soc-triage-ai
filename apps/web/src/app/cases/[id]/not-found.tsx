import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card p-6 space-y-3">
      <h2 className="text-base font-semibold">Case not found</h2>
      <p className="text-sm text-ink-dim">No case with that ID exists.</p>
      <Link href="/" className="text-blue-400 underline text-sm">
        ← back to dashboard
      </Link>
    </div>
  );
}
