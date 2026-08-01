"use client";

import { useState } from "react";
import Link from "next/link";
import { callModule1Offline, fetchCombinedPayload, type EssayInput } from "@/lib/api";
import type { CombinedModule3Payload, FetchState, Module1Result } from "@/lib/types";
import Module1CombineForm from "@/components/Module1CombineForm";
import Module1Panel from "@/components/Module1Panel";
import CombinedPanel from "@/components/CombinedPanel";
import RecommendationsPanel from "@/components/RecommendationsPanel";

const IDLE = { status: "idle", data: null, error: null } as const;

export default function Module1CombinePage() {
  const [essayId, setEssayId] = useState("");
  const [module1State, setModule1State] = useState<FetchState<Module1Result>>(IDLE);
  const [combinedState, setCombinedState] = useState<FetchState<CombinedModule3Payload>>(IDLE);

  const isLoading = module1State.status === "loading";

  async function handleSubmit(input: EssayInput, module2Json: File) {
    const newEssayId = `essay-${Date.now()}`;
    setEssayId(newEssayId);
    setModule1State({ status: "loading", data: null, error: null });
    setCombinedState({ status: "loading", data: null, error: null });

    let module1Result: Module1Result;
    try {
      module1Result = await callModule1Offline(input, module2Json, newEssayId);
      setModule1State({ status: "done", data: module1Result, error: null });
    } catch (err) {
      const message = (err as Error).message;
      setModule1State({ status: "error", data: null, error: message });
      setCombinedState({ status: "error", data: null, error: "Module 1 did not return a result." });
      return;
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
        <Link href="/" className="text-sm text-indigo-400 hover:text-indigo-300">
          ← Back
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-slate-100">Module 1 — Combine with Module 2 JSON</h1>
        <p className="mt-2 text-sm text-slate-400">
          Use this when only Module 1&apos;s backend is running on this machine (Module 2 does not need to
          be up at all). Provide the raw essay again, plus the JSON you downloaded earlier from the{" "}
          <Link href="/module2-only" className="text-indigo-400 hover:text-indigo-300">
            Module 2 page
          </Link>
          . Module 1 scores D2-D4 itself and merges it with that D1 data into the same combined result the
          main page produces.
        </p>
      </header>

      <div className="space-y-6">
        <Module1CombineForm onSubmit={handleSubmit} isLoading={isLoading} />

        {module1State.status !== "idle" && (
          <div className="space-y-6">
            <Module1Panel state={module1State} />
            <RecommendationsPanel state={combinedState} />
            <CombinedPanel state={combinedState} essayId={essayId} />
          </div>
        )}
      </div>
    </main>
  );
}