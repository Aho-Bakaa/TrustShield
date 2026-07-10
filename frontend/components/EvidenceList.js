"use client";
import { SeverityDot, IconShield } from "./ui";

const SEV_BORDER = {
  high: "border-l-rose-500 bg-rose-50/30",
  medium: "border-l-amber-500 bg-amber-50/30",
  low: "border-l-emerald-500 bg-emerald-50/30",
  info: "border-l-slate-400 bg-slate-50/60",
};

export default function EvidenceList({ evidence }) {
  if (!evidence?.length) return null;
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-slate-200 pb-3">
        <IconShield className="h-4 w-4 text-sebiTeal" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">Evidence ({evidence.length} signals)</h3>
      </div>
      <div className="space-y-2">
        {evidence.map((e, i) => {
          const borderStyle = SEV_BORDER[e.severity] || SEV_BORDER.info;
          return (
            <div key={i} className={`flex gap-3 rounded-xl border-l-[3px] border-y border-r border-slate-200 p-3 ${borderStyle}`}>
              <SeverityDot severity={e.severity} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-800">{e.label}</span>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold uppercase text-slate-500">{e.source}</span>
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-600">{e.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
