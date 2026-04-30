"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="card p-6 space-y-3 max-w-xl">
      <h2 className="text-base font-semibold text-red-400">Something went wrong</h2>
      <p className="text-sm text-ink-dim">{error.message}</p>
      <button
        onClick={reset}
        className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-3 py-1.5 rounded"
      >
        Try again
      </button>
    </div>
  );
}
