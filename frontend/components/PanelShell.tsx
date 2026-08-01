import type { ReactNode } from "react";

export default function PanelShell({
  title,
  subtitle,
  status,
  error,
  children,
}: {
  title: string;
  subtitle?: string;
  status: "loading" | "done" | "error";
  error?: string | null;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-sm">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
        </div>
        {status === "loading" && (
          <span className="flex items-center gap-2 text-xs font-medium text-indigo-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400" />
            Working...
          </span>
        )}
        {status === "error" && (
          <span className="rounded-full bg-rose-500/20 px-2.5 py-0.5 text-xs font-medium text-rose-300">
            Failed
          </span>
        )}
        {status === "done" && (
          <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-medium text-emerald-300">
            Done
          </span>
        )}
      </div>

      {status === "error" ? (
        <p className="rounded-lg border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-300">
          {error ?? "Something went wrong."}
        </p>
      ) : (
        children
      )}
    </section>
  );
}