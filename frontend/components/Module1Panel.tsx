import type { FetchState, Module1Result } from "@/lib/types";
import PanelShell from "./PanelShell";
import ScoreBadge from "./ScoreBadge";

const DIMENSION_LABELS: Record<string, string> = {
  D1: "Historical Accuracy",
  D2: "Coherence & Idea Flow",
  D3: "Vocabulary Richness",
  D4: "Structural Adherence",
};

export default function Module1Panel({ state }: { state: FetchState<Module1Result> }) {
  if (state.status === "loading") {
    return <PanelShell title="Module 1 — Writing Quality (D2-D4)" status="loading" />;
  }
  if (state.status === "error") {
    return <PanelShell title="Module 1 — Writing Quality (D2-D4)" status="error" error={state.error} />;
  }
  if (state.status === "idle" || !state.data) return null;

  const r = state.data;

  return (
    <PanelShell
      title="Module 1 — Writing Quality (D2-D4)"
      subtitle={`Average score: ${r.average_score} / 5  ·  ${r.word_count} words  ·  scorer: ${r.model_type}`}
      status="done"
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(["D1", "D2", "D3", "D4"] as const).map((code) => (
          <div key={code} className="rounded-lg border border-slate-800 bg-slate-950 p-3">
            <p className="text-xs text-slate-400">{DIMENSION_LABELS[code]}</p>
            <div className="mt-1">
              <ScoreBadge score={r.scores[code]} />
            </div>
          </div>
        ))}
      </div>

      <p className="mt-4 text-sm text-slate-300">{r.summary_si}</p>

      <p className="mt-3 text-xs text-slate-500">
        Weakest area: <span className="font-medium text-slate-300">{DIMENSION_LABELS[r.weakest] ?? r.weakest}</span>
      </p>
    </PanelShell>
  );
}