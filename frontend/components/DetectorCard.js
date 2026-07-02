"use client";
import { Bar } from "./ui";

const TITLES = {
  phishing: "Phishing / Impersonation Engine",
  social: "Social Manipulation Engine",
  voice: "Synthetic Voice Engine",
};

function Field({ k, v }) {
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return null;
  let display = v;
  if (typeof v === "boolean") display = v ? "Yes" : "No";
  else if (Array.isArray(v)) display = v.join(", ");
  else if (typeof v === "object") return null;
  return (
    <div className="flex justify-between gap-4 border-b border-edge/50 py-1.5 text-sm last:border-0">
      <span className="text-slate-400">{k.replace(/_/g, " ")}</span>
      <span className="text-right font-medium text-slate-200">{String(display)}</span>
    </div>
  );
}

export default function DetectorCard({ detector }) {
  if (!detector) return null;
  const f = detector.fields || {};
  const rendered = f.rendered;
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          {TITLES[detector.name] || detector.name}
        </h3>
        <div className="flex gap-1.5">
          {detector.used_llm && <span className="chip !text-[10px] text-indigo-300">LLM reasoning</span>}
          {detector.used_render && <span className="chip !text-[10px] text-sky-300">Rendered</span>}
        </div>
      </div>

      <div className="mb-3">
        <Bar value={detector.probability} label={`${detector.label}`} />
      </div>

      <p className="mb-3 text-sm text-slate-300">{detector.explanation}</p>

      <div className="rounded-xl bg-panel2/60 px-3">
        {Object.entries(f)
          .filter(([k]) => k !== "rendered" && k !== "features")
          .map(([k, v]) => (
            <Field key={k} k={k} v={v} />
          ))}
      </div>

      {f.features && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-slate-400">Signal features</summary>
          <div className="mt-2 rounded-xl bg-panel2/60 px-3">
            {Object.entries(f.features).map(([k, v]) => (
              <Field key={k} k={k} v={v} />
            ))}
          </div>
        </details>
      )}

      {rendered && (
        <details className="mt-3 text-sm" open>
          <summary className="cursor-pointer text-slate-400">Rendered-page evidence ({rendered.method})</summary>
          <div className="mt-2 rounded-xl bg-panel2/60 px-3">
            <Field k="final url" v={rendered.final_url} />
            <Field k="title" v={rendered.title} />
            <Field k="captures sensitive" v={rendered.captures_sensitive} />
            <Field k="has login form" v={rendered.has_login_form} />
            {rendered.redirect_chain?.length > 1 && (
              <Field k="redirect chain" v={rendered.redirect_chain.join("  ->  ")} />
            )}
          </div>
        </details>
      )}
    </div>
  );
}
