"use client";
import { useState, useEffect } from "react";
import IntakeForm from "@/components/IntakeForm";
import EvidenceList from "@/components/EvidenceList";
import TracePanel from "@/components/TracePanel";
import { LevelChip, RiskGauge, Bar, LEVEL_STYLES } from "@/components/ui";
import { getHealth } from "@/lib/api";

const PHASES = ["Classifying input type", "Analyzing content", "Rendering linked pages", "Verifying claims across web", "Producing verdict"];

function VerdictHeader({ result }) {
  const s = LEVEL_STYLES[result.risk_level];
  const isQuery = result.channel_type === "query";

  return (
    <div className={`rounded-2xl border bg-white p-8 ${s ? s.ring : ""}`}>
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <RiskGauge score={result.risk_score} level={result.risk_level} />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <LevelChip level={result.risk_level} />
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-500">
              {isQuery ? "question" : result.channel_type === "query" ? "image/file" : result.channel_type}
            </span>
          </div>
          <h2 className={`text-lg font-extrabold tracking-tight ${s ? s.text : "text-slate-800"}`}>{result.threat_label}</h2>
          <p className="text-sm leading-relaxed text-slate-600">{result.summary}</p>
          <div className="max-w-xs"><Bar value={result.confidence} label="Confidence" /></div>
        </div>
      </div>
      <div className={`mt-5 rounded-xl border border-slate-200 p-4 ${s ? s.bg : ""}`}>
        <p className="text-xs font-bold text-slate-700">{result.recommended_action}</p>
      </div>
    </div>
  );
}

export default function Scanner() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [phase, setPhase] = useState(0);
  const [startedAt, setStartedAt] = useState(null);

  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth({ status: "down" })); }, []);
  useEffect(() => {
    if (!loading) { setPhase(0); setStartedAt(null); return; }
    setStartedAt(Date.now());
    const interval = setInterval(() => setPhase(p => p < PHASES.length - 1 ? p + 1 : p), 4000);
    return () => clearInterval(interval);
  }, [loading]);

  const isQuery = result?.channel_type === "query";
  const hasLinks = result?.links?.length > 0;
  const isRendered = result?.detectors?.[0]?.used_render;
  const hasEntities = result?.entities?.length > 0;

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <div className="mb-10">
        <h1 className="text-2xl font-extrabold tracking-tight text-sebiNavy">TrustShield Scanner</h1>
        <p className="mt-2 text-sm text-slate-500">
          Paste a message, URL, query, or upload audio. The system classifies the input, searches the web to verify claims, and produces a verdict.
        </p>
      </div>

      <IntakeForm
        onStart={() => { setLoading(true); setError(""); setResult(null); }}
        onResult={(r) => { setResult(r); setLoading(false); }}
        onError={(e) => { setError(e); setLoading(false); }}
      />

      <div className="mt-8 space-y-6">
        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center">
            <div className="mx-auto mb-6 h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-sebiTeal" />
            <h3 className="text-sm font-bold text-slate-700">Analyzing</h3>
            <p className="mt-1 text-xs text-slate-500">
              {PHASES[phase]} {startedAt ? `(${Math.round((Date.now() - startedAt) / 1000)}s)` : ""}
            </p>
            <div className="mt-6 flex justify-center gap-2">
              {PHASES.map((_, i) => (
                <div key={i} className={`h-1.5 w-12 rounded-full transition-colors duration-500 ${i <= phase ? "bg-sebiTeal" : "bg-slate-200"}`} />
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6">
            <div className="flex items-center gap-2 text-sm font-bold text-rose-700">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
              Analysis failed
            </div>
            <p className="mt-2 text-sm text-rose-800">{error}</p>
          </div>
        )}

        {result && (
          <>
            <VerdictHeader result={result} />

            <EvidenceList evidence={result.evidence?.filter(e => e.source !== "search") || []} />

            {hasLinks && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6">
                <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Linked Pages Analyzed</h3>
                <div className="space-y-2">
                  {result.links.map((l, i) => (
                    <div key={i} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                      <span className={`h-2 w-2 rounded-full ${l.allowlisted ? "bg-emerald-500" : l.suspicious ? "bg-rose-500" : "bg-slate-400"}`} />
                      <span className="font-mono text-slate-700 truncate">{l.raw}</span>
                      {l.allowlisted && <span className="ml-auto shrink-0 rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700">OFFICIAL</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {hasEntities && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6">
                <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Entities Detected</h3>
                <div className="flex flex-wrap gap-2">
                  {result.entities.map((e, i) => (
                    <span key={i} className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700">{e.text}</span>
                  ))}
                </div>
              </div>
            )}

            <TracePanel trace={result.trace} escalated={result.escalated} latency={result.latency_ms} />
          </>
        )}
      </div>
    </main>
  );
}
