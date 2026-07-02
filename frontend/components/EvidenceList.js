"use client";
import { SeverityDot } from "./ui";

export default function EvidenceList({ evidence }) {
  if (!evidence?.length) return null;
  return (
    <div className="card p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
        Evidence ({evidence.length})
      </h3>
      <ul className="space-y-3">
        {evidence.map((e, i) => (
          <li key={i} className="flex gap-3">
            <SeverityDot severity={e.severity} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-slate-100">{e.label}</span>
                <span className="chip !py-0.5 !text-[10px] uppercase">{e.source}</span>
                {e.weight < 0 && (
                  <span className="text-[10px] font-semibold text-emerald-400">trust +</span>
                )}
              </div>
              <p className="mt-0.5 break-words text-sm text-slate-400">{e.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
