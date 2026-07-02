"use client";
import { Bar } from "./ui";

export default function AuthenticityCard({ auth }) {
  if (!auth) return null;
  const verified = auth.is_official_source;
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Authenticity Verification
        </h3>
        <span
          className={`chip !text-[11px] font-semibold ${
            verified ? "text-emerald-300" : "text-slate-300"
          }`}
        >
          {verified ? "✓ Verified official source" : "Unverified"}
        </span>
      </div>

      <div className="mb-3">
        <Bar value={auth.official_confidence} label="Official-source confidence" />
      </div>

      {auth.matched_entity && (
        <p className="mb-2 text-sm text-slate-300">
          Matched entity: <span className="font-medium text-emerald-300">{auth.matched_entity}</span>
        </p>
      )}

      <ul className="space-y-1.5">
        {auth.signals?.map((s, i) => (
          <li key={i} className="flex gap-2 text-sm text-slate-400">
            <span className="text-slate-600">•</span>
            <span>{s}</span>
          </li>
        ))}
      </ul>

      <div className="mt-3 flex gap-2 text-xs">
        <span className="chip">
          Provenance: {auth.provenance_available ? "present" : "absent (C2PA/DKIM)"}
        </span>
      </div>
    </div>
  );
}
