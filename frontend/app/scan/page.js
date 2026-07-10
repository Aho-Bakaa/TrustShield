"use client";
import { useState, useEffect } from "react";
import IntakeForm from "@/components/IntakeForm";
import EvidenceList from "@/components/EvidenceList";
import DetectorCard from "@/components/DetectorCard";
import AuthenticityCard from "@/components/AuthenticityCard";
import TracePanel from "@/components/TracePanel";
import { LevelChip, RiskGauge, Bar, LEVEL_STYLES } from "@/components/ui";
import { getHealth } from "@/lib/api";

const STEPS = [
  { label: "Ingestion Normalized", icon: "◉" },
  { label: "Intent Classification", icon: "◆" },
  { label: "Playwright Sandbox", icon: "◇" },
  { label: "Analytical Fusion", icon: "◎" },
];

export default function Scanner() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [step, setStep] = useState(0);

  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth({ status: "down" })); }, []);
  useEffect(() => {
    if (!loading) { setStep(0); return; }
    const t = setInterval(() => setStep(s => s < 3 ? s + 1 : s), 900);
    return () => clearInterval(t);
  }, [loading]);

  const s = result ? LEVEL_STYLES[result.risk_level] : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-6">
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sebiTeal/10 text-sebiTeal">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
        </div>
        <div>
          <h1 className="text-xl font-extrabold tracking-tight text-sebiNavy">Communication Scanner</h1>
          <p className="text-xs text-slate-500">Submit text, URLs, or media for threat analysis</p>
        </div>
        <div className="ml-auto flex items-center gap-3 text-[10px] font-bold">
          <span className={`flex items-center gap-1 rounded border px-2 py-1 ${health?.status === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
            VERIFIER: {health?.status === "ok" ? "ONLINE" : "OFFLINE"}
          </span>
          {health?.llm && (
            <span className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-slate-500">
              {health.llm.provider.toUpperCase()}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[420px_minmax(0,1fr)]">
        <div className="space-y-6">
          <IntakeForm
            onStart={() => { setLoading(true); setError(""); setResult(null); }}
            onResult={(r) => { setResult(r); setLoading(false); }}
            onError={(e) => { setError(e); setLoading(false); }}
          />

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Pipeline Stages</h3>
            <div className="space-y-2">
              {STEPS.map((s, i) => (
                <div key={i} className={`flex items-center gap-3 rounded-md px-3 py-2 text-xs ${loading && step >= i ? "bg-sebiTeal/5 text-sebiTeal" : "text-slate-400"}`}>
                  <span className={`text-sm ${loading && step >= i ? "animate-pulse" : ""}`}>{s.icon}</span>
                  <span className="font-semibold">{s.label}</span>
                  {loading && step === i && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-sebiTeal animate-ping" />}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {!result && !loading && !error && (
            <div className="flex min-h-[400px] flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-white/50 p-10 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
              </div>
              <h3 className="text-sm font-bold text-slate-600">Awaiting Submission</h3>
              <p className="mt-2 max-w-sm text-xs text-slate-400">Paste a message, URL, or upload audio/image in the scanner panel to begin analysis.</p>
            </div>
          )}

          {loading && (
            <div className="flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-10 text-center">
              <div className="scanner-bar absolute left-0 right-0 top-0 h-1 w-full" />
              <div className="mb-4 flex gap-1.5">
                {[0, 1, 2].map(i => (
                  <span key={i} className="h-3 w-3 animate-pulse rounded-full bg-sebiTeal" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
              <h3 className="text-sm font-bold uppercase tracking-widest text-slate-600">Analysis in Progress</h3>
              <div className="mt-4 rounded-lg bg-slate-900 p-4 text-left font-mono text-[10px] text-slate-300 w-72">
                {STEPS.map((s, i) => (
                  <div key={i} className="flex items-center gap-2 py-0.5">
                    <span className={step >= i ? "text-emerald-400" : i === step ? "text-amber-400 animate-pulse" : "text-slate-600"}>
                      {step >= i ? "✓" : i === step ? "…" : "○"}
                    </span>
                    <span className={step >= i ? "text-slate-200" : "text-slate-600"}>[{String(i + 1).padStart(2, "0")}] {s.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-rose-900">
              <div className="flex items-center gap-2 border-b border-rose-100 pb-3 text-xs font-bold uppercase tracking-wider text-rose-700">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                Pipeline Error
              </div>
              <p className="mt-3 text-xs leading-relaxed font-semibold">{error}</p>
              <p className="mt-2 text-[10px] text-rose-600">Verify the backend is running at {process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000"}</p>
            </div>
          )}

          {result && (
            <>
              <div className={`rounded-xl border bg-white p-6 ${s ? s.ring : ""}`}>
                <div className="flex flex-col items-center gap-6 sm:flex-row">
                  <RiskGauge score={result.risk_score} level={result.risk_level} />
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <LevelChip level={result.risk_level} />
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-500">{result.channel_type}</span>
                      {result.escalated && <span className="rounded bg-indigo-50 px-2 py-0.5 text-[9px] font-bold uppercase text-indigo-700">Deep Analysis Active</span>}
                    </div>
                    <h2 className={`text-lg font-extrabold tracking-tight ${s ? s.text : ""}`}>{result.threat_label}</h2>
                    <p className="text-xs leading-relaxed text-slate-600 font-semibold">{result.summary}</p>
                    <div className="max-w-xs pt-1"><Bar value={result.confidence} label="Confidence" /></div>
                  </div>
                </div>
                <div className={`mt-4 rounded-lg border border-slate-200 p-4 ${s ? s.bg : ""}`}>
                  <div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">Recommended Action</div>
                  <p className="text-xs leading-relaxed text-slate-700 font-bold">{result.recommended_action}</p>
                </div>
              </div>

              {result.entities?.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-5">
                  <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Detected Market Entities</h3>
                  <div className="flex flex-wrap gap-2">
                    {result.entities.map((e, i) => (
                      <div key={i} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs">
                        <span className="font-bold text-slate-800">{e.text}</span>
                        <span className="text-slate-400">({e.type})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <EvidenceList evidence={result.evidence} />
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <DetectorCard detector={result.detectors?.[0]} />
                <AuthenticityCard auth={result.authenticity} />
              </div>
              <TracePanel trace={result.trace} escalated={result.escalated} latency={result.latency_ms} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
