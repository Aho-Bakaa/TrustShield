"use client";
import { useState } from "react";
import { Bar, IconCpu, IconGlobe } from "./ui";

const TITLES = {
  phishing: "Dynamic Phishing & Impersonation Analyzer",
  social: "Social Manipulation Detection Engine",
  voice: "Neural Synthetic Voice Scanner",
};

function Field({ k, v }) {
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return null;
  let display = v;
  if (typeof v === "boolean") {
    display = v ? (
      <span className="inline-flex items-center rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-850 border border-rose-200">TRUE</span>
    ) : (
      <span className="inline-flex items-center rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-850 border border-emerald-200">FALSE</span>
    );
  }
  else if (Array.isArray(v)) display = v.join(", ");
  else if (typeof v === "object") return null;
  
  return (
    <div className="flex justify-between gap-4 border-b border-slate-200 py-2.5 text-xs last:border-0">
      <span className="font-bold uppercase tracking-wider text-slate-500 text-[10px]">{k.replace(/_/g, " ")}</span>
      <span className="text-right font-mono font-bold text-slate-700 break-all max-w-[70%]">{display}</span>
    </div>
  );
}

export default function DetectorCard({ detector }) {
  const [featuresOpen, setFeaturesOpen] = useState(false);
  const [renderedOpen, setRenderedOpen] = useState(true);

  if (!detector) return null;
  const f = detector.fields || {};
  const rendered = f.rendered;

  return (
    <div className="card overflow-hidden p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          {TITLES[detector.name] || detector.name}
        </h3>
        <div className="flex gap-1.5">
          {detector.used_llm && (
            <span className="inline-flex items-center gap-1 rounded bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-indigo-700">
              <IconCpu className="h-2.5 w-2.5" />
              LLM Reasoning
            </span>
          )}
          {detector.used_render && (
            <span className="inline-flex items-center gap-1 rounded bg-sky-50 border border-sky-200 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-sky-700">
              <IconGlobe className="h-2.5 w-2.5" />
              Rendered
            </span>
          )}
        </div>
      </div>

      {/* Probabilty Gauge */}
      <div className="mb-4">
        <Bar value={detector.probability} label={`Threat Probability (${detector.label || "Estimated"})`} />
      </div>

      {/* Explanation */}
      <p className="mb-4 text-xs leading-relaxed text-slate-650 bg-slate-50 border border-slate-200 rounded-xl p-3 font-medium">
        {detector.explanation}
      </p>

      {/* Modality Specific Details */}
      <div className="rounded-xl bg-slate-50 border border-slate-200 px-4 py-1">
        {Object.entries(f)
          .filter(([k]) => k !== "rendered" && k !== "features")
          .map(([k, v]) => (
            <Field key={k} k={k} v={v} />
          ))}
      </div>

      {/* Signal Features (Collapsible) */}
      {f.features && (
        <div className="mt-3 border border-slate-200 rounded-xl overflow-hidden bg-slate-50">
          <button 
            onClick={() => setFeaturesOpen(!featuresOpen)}
            className="flex w-full items-center justify-between px-4 py-3 text-xs font-bold text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <span className="uppercase tracking-wider">Signal Features Extracted</span>
            <svg 
              className={`h-4 w-4 transform transition-transform duration-200 ${featuresOpen ? "rotate-180" : ""}`} 
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          
          {featuresOpen && (
            <div className="border-t border-slate-200 bg-white px-4 py-1">
              {Object.entries(f.features).map(([k, v]) => (
                <Field key={k} k={k} v={v} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Rendered Page Evidence (Collapsible) */}
      {rendered && (
        <div className="mt-3 border border-slate-200 rounded-xl overflow-hidden bg-slate-50">
          <button 
            onClick={() => setRenderedOpen(!renderedOpen)}
            className="flex w-full items-center justify-between px-4 py-3 text-xs font-bold text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <span className="uppercase tracking-wider">Dynamic Render Sandbox Proof</span>
            <svg 
              className={`h-4 w-4 transform transition-transform duration-200 ${renderedOpen ? "rotate-180" : ""}`} 
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {renderedOpen && (
            <div className="border-t border-slate-200 bg-white px-4 py-1">
              <Field k="Execution Sandbox" v={rendered.method} />
              <Field k="Final Redirect URL" v={rendered.final_url} />
              <Field k="Page Header Title" v={rendered.title} />
              <Field k="Sensitive Capture Detect" v={rendered.captures_sensitive} />
              <Field k="Detected Auth Form" v={rendered.has_login_form} />
              {rendered.redirect_chain?.length > 1 && (
                <Field k="HTTP Redirect Chain" v={rendered.redirect_chain.join("  →  ")} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
