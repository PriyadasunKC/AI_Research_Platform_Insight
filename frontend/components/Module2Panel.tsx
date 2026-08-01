import type { FetchState, Module2Claim, Module2Result } from "@/lib/types";
import PanelShell from "./PanelShell";
import JsonBlock from "./JsonBlock";

const VERDICT_STYLES: Record<Module2Claim["verdict"], string> = {
  CORRECT: "border-emerald-800 bg-emerald-950/40 text-emerald-300",
  INCORRECT: "border-rose-800 bg-rose-950/40 text-rose-300",
  UNVERIFIABLE: "border-slate-700 bg-slate-950 text-slate-400",
};

export default function Module2Panel({
  state,
  showJsonExport = false,
  downloadName = "module2_result.json",
}: {
  state: FetchState<Module2Result>;
  /** Adds a "raw JSON" block with Copy/Download — off by default so the
   * combined-flow page (which already has its own Combined Output JSON
   * panel) doesn't change. Turned on for the standalone Module 2 page. */
  showJsonExport?: boolean;
  downloadName?: string;
}) {
  if (state.status === "loading") {
    return <PanelShell title="Module 2 — Historical Accuracy (D1)" status="loading" />;
  }
  if (state.status === "error") {
    return <PanelShell title="Module 2 — Historical Accuracy (D1)" status="error" error={state.error} />;
  }
  if (state.status === "idle" || !state.data) return null;

  const r = state.data;

  return (
    <PanelShell
      title="Module 2 — Historical Accuracy (D1)"
      subtitle={
        r.essay_subject
          ? `Subject: ${r.essay_subject}  ·  ${r.processing_seconds}s`
          : `${r.processing_seconds}s`
      }
      status="done"
    >
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        <Stat label="Accuracy" value={r.accuracy_score !== null ? `${r.accuracy_score}%` : "N/A"} />
        <Stat label="Confidence" value={r.confidence_level} />
        <Stat label="Correct" value={String(r.correct_claims)} />
        <Stat label="Incorrect" value={String(r.incorrect_claims)} />
        <Stat label="Unverifiable" value={String(r.unverifiable_claims)} />
        <Stat label="Editorial" value={String(r.editorial_claims)} />
      </div>

      {r.coverage_warning && (
        <p className="mt-3 rounded-lg border border-amber-800 bg-amber-950/30 p-3 text-xs text-amber-300">
          Knowledge Graph coverage for this essay is low ({Math.round(r.coverage_ratio * 100)}%) — this
          score is based on limited evidence.
        </p>
      )}

      {r.claims.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-slate-400">Claim-by-claim verdicts (LLM output)</p>
          <div className="max-h-80 space-y-2 overflow-auto pr-1">
            {r.claims.map((claim, i) => (
              <div key={i} className={`rounded-lg border p-3 text-sm ${VERDICT_STYLES[claim.verdict]}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide">{claim.verdict}</span>
                </div>
                <p className="mt-1 text-slate-200">{claim.claim_sinhala}</p>
                <p className="mt-1 text-xs opacity-80">{claim.explanation}</p>
                {claim.teacher_feedback && (
                  <p className="mt-2 rounded-md bg-black/20 p-2 text-xs text-slate-200">
                    {claim.teacher_feedback}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {showJsonExport && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-slate-400">
            Raw JSON — download this to use on the Module 1 combine page
          </p>
          <JsonBlock data={r} downloadName={downloadName} />
        </div>
      )}
    </PanelShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-100">{value}</p>
    </div>
  );
}