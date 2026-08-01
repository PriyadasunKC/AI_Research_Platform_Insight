import type { CombinedModule3Payload, DimensionNote, FetchState } from "@/lib/types";
import PanelShell from "./PanelShell";

/** Synthesizes plain-language, actionable recommendations from the combined
 * payload's per-dimension notes — this deliberately does NOT dump the raw
 * JSON at the reader; it turns each dimension's how_to_improve/short_note_si
 * into a readable card, weakest area first. */
export default function RecommendationsPanel({ state }: { state: FetchState<CombinedModule3Payload> }) {
  if (state.status === "loading") {
    return <PanelShell title="Recommendations" status="loading" />;
  }
  if (state.status === "error") {
    return <PanelShell title="Recommendations" status="error" error={state.error} />;
  }
  if (state.status === "idle" || !state.data) return null;

  const { notes, weakest_area } = state.data;

  const entries = Object.entries(notes)
    .filter(([, note]) => note && (note.how_to_improve || note.short_note_si))
    .sort(([, a], [, b]) => {
      const scoreA = a.score ?? Number.POSITIVE_INFINITY;
      const scoreB = b.score ?? Number.POSITIVE_INFINITY;
      return scoreA - scoreB;
    });

  if (entries.length === 0) {
    return (
      <PanelShell title="Recommendations" status="done">
        <p className="text-sm text-slate-400">No specific recommendations were generated for this essay.</p>
      </PanelShell>
    );
  }

  return (
    <PanelShell
      title="Recommendations"
      subtitle="What to work on next, ordered from most to least important"
      status="done"
    >
      {weakest_area && (
        <div className="mb-4 rounded-lg border border-indigo-700 bg-indigo-950/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-300">
            Focus area: {weakest_area.dimension}
          </p>
          {weakest_area.hint && <p className="mt-1 text-sm text-slate-200">{weakest_area.hint}</p>}
        </div>
      )}

      <div className="space-y-3">
        {entries.map(([label, note]) => (
          <RecommendationCard key={label} label={label} note={note} />
        ))}
      </div>
    </PanelShell>
  );
}

function RecommendationCard({ label, note }: { label: string; note: DimensionNote }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-slate-100">{label}</p>
        {note.score !== null && note.score !== undefined && (
          <span className="text-xs text-slate-400">{note.score} / 5</span>
        )}
      </div>
      {note.how_to_improve && <p className="mt-2 text-sm text-slate-300">{note.how_to_improve}</p>}
      {note.short_note_si && <p className="mt-1 text-sm text-slate-400">{note.short_note_si}</p>}
    </div>
  );
}