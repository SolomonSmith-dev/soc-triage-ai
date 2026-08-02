export default function Loading() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-12 bg-bg-elev rounded" />
      <div className="grid grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-20 bg-bg-elev rounded" />
        ))}
      </div>
      <div className="h-32 bg-bg-elev rounded" />
      <div className="h-48 bg-bg-elev rounded" />
    </div>
  );
}
