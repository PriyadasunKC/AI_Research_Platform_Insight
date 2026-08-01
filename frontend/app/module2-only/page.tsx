"use client";

import { useState } from "react";
import Link from "next/link";
import { callModule2, type EssayInput } from "@/lib/api";
import type { FetchState, Module2Result } from "@/lib/types";
import EssayForm from "@/components/EssayForm";
import Module2Panel from "@/components/Module2Panel";

const IDLE = { status: "idle", data: null, error: null } as const;

export default function Module2OnlyPage() {
  const [essayId, setEssayId] = useState("");
  const [module2State, setModule2State] = useState<FetchState<Module2Result>>(IDLE);

  async function handleSubmit(input: EssayInput) {
    const newEssayId = `essay-${Date.now()}`;
    setEssayId(newEssayId);
    setModule2State({ status: "loading", data: null, error: null });

    try {
      const data = await callModule2(input, newEssayId);
      setModule2State({ status: "done", data, error: null });
    } catch (err) {
      setModule2State({ status: "error", data: null, error: (err as Error).message });
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-10">
      <header className="mb-8">
        <Link href="/" className="text-sm text-indigo-400 hover:text-indigo-300">
          ← Back
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-slate-100">Module 2  Historical Accuracy Only</h1>
        <p className="mt-2 text-sm text-slate-400">
          Run Module 2 by itself - no dependency on Module 1 being up. Use this when only Module 2&apos;s
          backend is running on this machine. Download the result JSON below and use it on the{" "}
          <Link href="/module1-combine" className="text-indigo-400 hover:text-indigo-300">
            Module 1 combine page
          </Link>{" "}
          later, once you switch to running Module 1 instead.
        </p>
      </header>

      <div className="space-y-6">
        <EssayForm onSubmit={handleSubmit} isLoading={module2State.status === "loading"} />

        {module2State.status !== "idle" && (
          <Module2Panel
            state={module2State}
            showJsonExport
            downloadName={`module2_result_${essayId}.json`}
          />
        )}
      </div>
    </main>
  );
}