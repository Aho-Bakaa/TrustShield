"use client";
import { Bar, IconCheck, IconAlert, IconLock } from "./ui";

export default function AuthenticityCard({ auth }) {
  if (!auth) return null;
  const verified = auth.is_official_source;
  
  return (
    <div className="card overflow-hidden p-5">
      <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <IconLock className="h-4.5 w-4.5 text-sebiTeal" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Source Authenticity Protocol
          </h3>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${
            verified 
              ? "bg-emerald-100 text-emerald-800 border-emerald-200" 
              : "bg-slate-100 text-slate-500 border-slate-200"
          }`}
        >
          {verified ? (
            <>
              <IconCheck className="h-3 w-3" />
              Verified Official
            </>
          ) : (
            <>
              <IconAlert className="h-3 w-3 text-slate-500" />
              Unverified
            </>
          )}
        </span>
      </div>

      <div className="mb-4">
        <Bar value={auth.official_confidence} label="Official-Source Match Confidence" />
      </div>

      {auth.matched_entity && (
        <div className="mb-4 rounded-xl bg-slate-50 border border-slate-200 p-3">
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Registry Entity Match</div>
          <div className="mt-1 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-bold text-sm text-emerald-700">{auth.matched_entity}</span>
          </div>
        </div>
      )}

      {auth.signals?.length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1">Authenticity Signals</div>
          <ul className="space-y-1.5">
            {auth.signals.map((s, i) => (
              <li key={i} className="flex items-start gap-2.5 rounded-lg bg-slate-50 px-3 py-2 text-xs border border-slate-200 text-slate-700 font-medium">
                <span className="mt-0.5 text-emerald-600">
                  <IconCheck className="h-3.5 w-3.5" />
                </span>
                <span className="leading-normal">{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 flex items-center gap-2 border-t border-slate-200 pt-3">
        <div className="text-[10px] text-slate-500 font-bold">Cryptographic Provenance (C2PA/DKIM):</div>
        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
          auth.provenance_available 
            ? "bg-sky-100 text-sky-850 border border-sky-200" 
            : "bg-slate-100 text-slate-500 border border-slate-200"
        }`}>
          {auth.provenance_available ? "SECURED (C2PA)" : "ABSENT / UNVERIFIED"}
        </span>
      </div>
    </div>
  );
}
