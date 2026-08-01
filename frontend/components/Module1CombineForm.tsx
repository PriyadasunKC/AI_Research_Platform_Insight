"use client";

import { useState } from "react";
import type { EssayInput } from "@/lib/api";

export default function Module1CombineForm({
  onSubmit,
  isLoading,
}: {
  onSubmit: (input: EssayInput, module2Json: File) => void;
  isLoading: boolean;
}) {
  const [mode, setMode] = useState<"text" | "file">("text");
  const [text, setText] = useState("");
  const [essayFile, setEssayFile] = useState<File | null>(null);
  const [module2File, setModule2File] = useState<File | null>(null);

  const essayReady = mode === "text" ? text.trim().length > 0 : essayFile !== null;
  const canSubmit = essayReady && module2File !== null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || isLoading || !module2File) return;
    onSubmit(mode === "text" ? { text } : { file: essayFile as File }, module2File);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-sm"
    >
      <div className="space-y-5">
        <div>
          <p className="mb-2 text-sm font-medium text-slate-300">1. Essay</p>
          <div className="mb-3 flex gap-2">
            <button
              type="button"
              onClick={() => setMode("text")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "text" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Type essay
            </button>
            <button
              type="button"
              onClick={() => setMode("file")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "file" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Upload file
            </button>
          </div>

          {mode === "text" ? (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste or type the Sinhala historical essay here..."
              rows={8}
              className="w-full resize-y rounded-lg border border-slate-700 bg-slate-950 p-4 text-sm leading-relaxed text-slate-100 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
              lang="si"
            />
          ) : (
            <div className="flex flex-col items-start gap-2">
              <input
                type="file"
                accept=".txt"
                onChange={(e) => setEssayFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-500"
              />
              {essayFile && <p className="text-sm text-slate-400">Selected: {essayFile.name}</p>}
            </div>
          )}
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-300">
            2. Module 2 result JSON (downloaded from the Module 2 page earlier)
          </p>
          <input
            type="file"
            accept=".json"
            onChange={(e) => setModule2File(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-500"
          />
          {module2File && <p className="mt-2 text-sm text-slate-400">Selected: {module2File.name}</p>}
        </div>
      </div>

      <button
        type="submit"
        disabled={!canSubmit || isLoading}
        className="mt-5 w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
      >
        {isLoading ? "Scoring & combining..." : "Score & Combine"}
      </button>
    </form>
  );
}