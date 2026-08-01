"use client";

import { useState } from "react";

export default function JsonBlock({
  data,
  downloadName,
}: {
  data: unknown;
  downloadName: string;
}) {
  const [copied, setCopied] = useState(false);
  const pretty = JSON.stringify(data, null, 2);

  async function handleCopy() {
    await navigator.clipboard.writeText(pretty);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function handleDownload() {
    const blob = new Blob([pretty], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-700 px-4 py-2">
        <span className="text-xs font-medium text-slate-400">JSON</span>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="rounded-md bg-slate-800 px-3 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
          >
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            onClick={handleDownload}
            className="rounded-md bg-slate-800 px-3 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
          >
            Download
          </button>
        </div>
      </div>
      <pre className="max-h-96 overflow-auto p-4 text-xs leading-relaxed text-emerald-300">
        {pretty}
      </pre>
    </div>
  );
}