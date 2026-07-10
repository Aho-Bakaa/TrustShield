"use client";
import { SeverityDot, IconShield } from "./ui";

const SEV_BORDER = {
  high: "border-l-rose-500 bg-rose-50/30 hover:bg-rose-50/50 border-y-slate-200 border-r-slate-200",
  medium: "border-l-amber-500 bg-amber-50/30 hover:bg-amber-50/50 border-y-slate-200 border-r-slate-200",
  low: "border-l-emerald-500 bg-emerald-50/30 hover:bg-emerald-50/50 border-y-slate-200 border-r-slate-200",
  info: "border-l-slate-400 bg-slate-50/60 hover:bg-slate-50/80 border-y-slate-200 border-r-slate-200",
};

export default function EvidenceList({ evidence }) {
  if (!evidence?.length) return null;
  return (
    <div className="card overflow-hidden p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-slate-200 pb-3">
        <IconShield className="h-4.5 w-4.5 text-sebiTeal" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
          Security Verification Audit Logs ({evidence.length})
        </h3>
      </div>
      <div className="space-y-2.5">
        {evidence.map((e, i) => {
          const borderStyle = SEV_BORDER[e.severity] || SEV_BORDER.info;
          const isNegative = e.weight < 0;
          return (
            <div 
              key={i} 
              className={`flex gap-4 rounded-xl border-l-[3.5px] border-y border-r p-4 transition-all duration-200 ${borderStyle}`}
            >
              <div className="mt-0.5">
                <SeverityDot severity={e.severity} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold tracking-wide text-slate-800">{e.label}</span>
                    <span className="rounded bg-slate-100 border border-slate-200 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500">
                      {e.source}
                    </span>
                  </div>
                  {e.weight !== 0 && (
                    <span 
                      className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[9px] font-bold tracking-tight ${
                        isNegative 
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-200" 
                          : "bg-rose-100 text-rose-800 border border-rose-200"
                      }`}
                    >
                      {isNegative ? "✓ Trust Boost" : "⚠ Risk Impact"} ({isNegative ? "" : "+"}{(e.weight * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>
                <p className="mt-1.5 break-words text-xs leading-relaxed text-slate-600 font-medium">{e.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
