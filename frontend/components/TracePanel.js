"use client";
import { IconTerminal, IconClock } from "./ui";

export default function TracePanel({ trace, escalated, latency }) {
  if (!trace?.length) return null;
  return (
    <div className="card overflow-hidden p-0">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 bg-slate-50/55">
        <div className="flex items-center gap-2.5">
          <IconTerminal className="h-4 w-4 text-sebiTeal" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-650">
            Pipeline Execution & Verification Trace
          </h3>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-bold">
          <span className={`rounded-md border px-2 py-0.5 uppercase tracking-wider ${
            escalated 
              ? "bg-indigo-100 text-indigo-800 border-indigo-200" 
              : "bg-slate-100 text-slate-600 border-slate-200"
          }`}>
            {escalated ? "Deep Verification Scan" : "Triage Analysis Mode"}
          </span>
          <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 text-slate-600 font-mono">
            <IconClock className="h-3 w-3 text-slate-400" />
            {latency} ms
          </span>
        </div>
      </div>

      {/* Terminal Mock Box */}
      <div className="bg-slate-900 p-4 font-mono text-[11px] leading-relaxed text-slate-400">
        {/* Window controls */}
        <div className="mb-4 flex items-center gap-1.5 border-b border-slate-800 pb-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-500/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
          <span className="ml-2 text-[9px] uppercase tracking-widest text-slate-500 font-bold">Verification Shell v1.0.0</span>
        </div>

        {/* Logs */}
        <div className="space-y-3.5 pl-1.5">
          {trace.map((t, i) => {
            let stageLabel = t.stage;
            let stageColor = "text-sky-400";
            if (t.stage.toLowerCase().includes("triage")) {
              stageLabel = "TRIAGE";
              stageColor = "text-amber-400";
            } else if (t.stage.toLowerCase().includes("intake") || t.stage.toLowerCase().includes("preprocess")) {
              stageLabel = "INTAKE";
              stageColor = "text-blue-400";
            } else if (t.stage.toLowerCase().includes("deep") || t.stage.toLowerCase().includes("render") || t.stage.toLowerCase().includes("llm")) {
              stageLabel = "DEEP_SCAN";
              stageColor = "text-indigo-400 animate-pulse";
            } else if (t.stage.toLowerCase().includes("fusion") || t.stage.toLowerCase().includes("decision")) {
              stageLabel = "FUSION";
              stageColor = "text-emerald-400";
            }

            return (
              <div key={i} className="relative border-l border-slate-800 pl-4 py-0.5 hover:border-slate-700 transition-colors">
                <span className="absolute -left-[3.5px] top-1.5 h-1.5 w-1.5 rounded-full bg-slate-700" />
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500">[{String(i+1).padStart(2, '0')}]</span>
                    <span className={`font-bold uppercase tracking-wider text-[10px] ${stageColor}`}>
                      {stageLabel}
                    </span>
                  </div>
                  {t.latency_ms > 0 && (
                    <span className="text-[10px] font-bold text-slate-500 tabular-nums">+{t.latency_ms}ms</span>
                  )}
                </div>
                <p className="mt-1 text-slate-200 text-[11px] leading-relaxed break-words font-mono">
                  {t.detail}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
