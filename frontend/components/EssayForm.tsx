"use client";

import { useRef, useState } from "react";
import type { EssayInput } from "@/lib/api";

export default function EssayForm({
  onSubmit,
  isLoading,
}: {
  onSubmit: (input: EssayInput) => void;
  isLoading: boolean;
}) {
  const [mode, setMode] = useState<"text" | "file">("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canSubmit = mode === "text" ? text.trim().length > 0 : file !== null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || isLoading) return;
    onSubmit(mode === "text" ? { text } : { file: file as File });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-sm"
    >
      <div className="mb-4 flex gap-2">
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
          rows={10}
          className="w-full resize-y rounded-lg border border-slate-700 bg-slate-950 p-4 text-sm leading-relaxed text-slate-100 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
          lang="si"
        />
      ) : (
        <div className="flex flex-col items-start gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-500"
          />
          {file && <p className="text-sm text-slate-400">Selected: {file.name}</p>}
        </div>
      )}

      <button
        type="submit"
        disabled={!canSubmit || isLoading}
        className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
      >
        {isLoading ? "Scoring essay..." : "Get Feedback for Essay"}
      </button>
    </form>
  );
}