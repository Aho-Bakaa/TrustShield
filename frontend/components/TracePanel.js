"use client";

export default function TracePanel({ trace, escalated, latency }) {
  if (!trace?.length) return null;
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Analyst Trace
        </h3>
        <div className="flex gap-2 text-xs">
          <span className="chip">{escalated ? "Escalated → deep analysis" : "Triage only"}</span>
          <span className="chip tabular-nums">{latency} ms</span>
        </div>
      </div>
      <ol className="relative ml-2 border-l border-edge">
        {trace.map((t, i) => (
          <li key={i} className="mb-3 ml-4">
            <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-sky-500" />
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold text-sky-300">{t.stage}</span>
              {t.latency_ms > 0 && (
                <span className="text-[10px] tabular-nums text-slate-500">{t.latency_ms} ms</span>
              )}
            </div>
            <p className="text-sm text-slate-400">{t.detail}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
