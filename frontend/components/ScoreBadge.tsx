export default function ScoreBadge({ score, max = 5 }: { score: number | null; max?: number }) {
  if (score === null) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-300">
        N/A
      </span>
    );
  }
  const ratio = score / max;
  const color =
    ratio >= 0.8
      ? "bg-emerald-500/20 text-emerald-300"
      : ratio >= 0.5
        ? "bg-amber-500/20 text-amber-300"
        : "bg-rose-500/20 text-rose-300";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${color}`}>
      {score} / {max}
    </span>
  );
}