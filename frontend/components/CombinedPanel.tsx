import type { CombinedModule3Payload, FetchState } from "@/lib/types";
import PanelShell from "./PanelShell";
import JsonBlock from "./JsonBlock";

export default function CombinedPanel({
  state,
  essayId,
}: {
  state: FetchState<CombinedModule3Payload>;
  essayId: string;
}) {
  if (state.status === "loading") {
    return <PanelShell title="Combined Output — for Module 3" status="loading" />;
  }
  if (state.status === "error") {
    return <PanelShell title="Combined Output — for Module 3" status="error" error={state.error} />;
  }
  if (state.status === "idle" || !state.data) return null;

  return (
    <PanelShell
      title="Combined Output — for Module 3"
      subtitle="All 4 dimensions (D1-D4) merged into the exact payload shape Module 3 consumes"
      status="done"
    >
      <JsonBlock data={state.data} downloadName={`module3_payload_${essayId}.json`} />
    </PanelShell>
  );
}