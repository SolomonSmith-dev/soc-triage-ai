export function MitreChip({ technique }: { technique: string }) {
  return (
    <span className="inline-block bg-blue-950 text-blue-300 font-mono text-xs font-medium px-2 py-0.5 rounded mr-1.5 mb-1.5">
      {technique}
    </span>
  );
}
