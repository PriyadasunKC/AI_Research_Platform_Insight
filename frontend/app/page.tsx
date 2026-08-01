"use client";

import { useState } from "react";
import { callModule1, fetchCombinedPayload, type EssayInput } from "@/lib/api";
import type { CombinedModule3Payload, FetchState, Module1Result, Module2Result } from "@/lib/types";
import EssayForm from "@/components/EssayForm";
import Module1Panel from "@/components/Module1Panel";
import Module2Panel from "@/components/Module2Panel";
import CombinedPanel from "@/components/CombinedPanel";
import RecommendationsPanel from "@/components/RecommendationsPanel";

const IDLE = { status: "idle", data: null, error: null } as const;

export default function Home() {
  const [essayId, setEssayId] = useState<string>("");
  const [module1State, setModule1State] = useState<FetchState<Module1Result>>(IDLE);
  const [module2State, setModule2State] = useState<FetchState<Module2Result>>(IDLE);
  const [combinedState, setCombinedState] = useState<FetchState<CombinedModule3Payload>>(IDLE);

  const hasResults = module1State.status !== "idle" || module2State.status !== "idle";
  const isLoading = module1State.status === "loading" || module2State.status === "loading";

  async function handleSubmit(input: EssayInput) {
    const newEssayId = `essay-${Date.now()}`;
    setEssayId(newEssayId);
    setModule1State({ status: "loading", data: null, error: null });
    setModule2State({ status: "loading", data: null, error: null });
    setCombinedState({ status: "loading", data: null, error: null });

    // Only Module 1 is called from the browser. Module 1's own /score call
    // ALSO calls Module 2 server-side (see module_1/app.py) and embeds the
    // full raw Module 2 response in module2_result — the Module 2 panel
    // reads from that instead of making its own separate call.
    //
    // Deliberately NOT calling Module 2 directly here anymore: it used to
    // fire in parallel purely so its panel could render slightly earlier,
    // but that meant Module 2 graded the SAME essay twice, concurrently
    // (once for this call, once for Module 1's server-side call) — doubling
    // its real workload for every single essay check and causing Module
    // 1's own call to occasionally time out on long essays. One call per
    // essay check is the correct tradeoff even though the Module 2 panel
    // now appears at the same time as Module 1's rather than earlier.
    const module1Result = await callModule1(input, newEssayId)
      .then((data) => {
        setModule1State({ status: "done", data, error: null });
        return data;
      })
      .catch((err: Error) => {
        setModule1State({ status: "error", data: null, error: err.message });
        setModule2State({
          status: "error",
          data: null,
          error: "Module 2 result unavailable — Module 1 did not return a result.",
        });
        return null;
      });

    if (!module1Result) {
      setCombinedState({
        status: "error",
        data: null,
        error: "Combined output unavailable — Module 1 did not return a result.",
      });
      return;
    }

    const m2 = module1Result.module2_result;
    if (m2.ok && m2.raw) {
      setModule2State({ status: "done", data: m2.raw, error: null });
    } else {
      setModule2State({ status: "error", data: null, error: m2.error ?? "Module 2 did not return a result." });
    }

    try {
      const combined = await fetchCombinedPayload(module1Result.module3_export.api_url);
      setCombinedState({ status: "done", data: combined, error: null });
    } catch (err) {
      setCombinedState({ status: "error", data: null, error: (err as Error).message });
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100">
          Sinhala Historical Essay Feedback
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Enter an essay (or upload a .txt file) to get writing-quality feedback (Module 1) and
          Knowledge-Graph-grounded historical-accuracy feedback (Module 2), combined into a single
          4-dimension result.
        </p>
      </header>

      <div className="space-y-6">
        <EssayForm onSubmit={handleSubmit} isLoading={isLoading} />

        {hasResults && (
          <div className="space-y-6">
            <Module1Panel state={module1State} />
            <Module2Panel state={module2State} />
            <RecommendationsPanel state={combinedState} />
            <CombinedPanel state={combinedState} essayId={essayId} />
          </div>
        )}
      </div>
    </main>
  );
}
