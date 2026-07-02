"use client";
import { useEffect, useState } from "react";
import IntakeForm from "@/components/IntakeForm";
import EvidenceList from "@/components/EvidenceList";
import DetectorCard from "@/components/DetectorCard";
import AuthenticityCard from "@/components/AuthenticityCard";
import TracePanel from "@/components/TracePanel";
import { LevelChip, RiskGauge, Bar, LEVEL_STYLES } from "@/components/ui";
import { getHealth } from "@/lib/api";

export default function Home() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);

  const s = result ? LEVEL_STYLES[result.risk_level] : null;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-indigo-500 text-lg">🛡️</div>
            <h1 className="text-2xl font-bold tracking-tight">TrustShield</h1>
            <span className="chip !text-[10px]">Securities Markets · PS1</span>
          </div>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Multimodal trust layer — detects AI-generated phishing, synthetic voice, and social
            manipulation, and verifies authentic official communications.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 text-xs">
          <span className={`chip ${health?.status === "ok" ? "text-emerald-300" : "text-rose-300"}`}>
            API {health?.status === "ok" ? "online" : health ? "offline" : "…"}
          </span>
          {health?.llm && (
            <span className="chip text-slate-400">
              Reasoning: {health.llm.provider} · {health.llm.mode?.includes("mock") ? "rule-based" : "live"}
            </span>
          )}
          {health?.llm && (
            <span className={`chip ${health.llm.vision_available ? "text-emerald-300" : "text-slate-500"}`}>
              Vision: {health.llm.vision_available ? "on" : "off"}
            </span>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        {/* Left — intake */}
        <div className="space-y-6">
          <IntakeForm
            onStart={() => {
              setLoading(true);
              setError("");
              setResult(null);
            }}
            onResult={(r) => {
              setResult(r);
              setLoading(false);
            }}
            onError={(e) => {
              setError(e);
              setLoading(false);
            }}
          />

          <div className="card p-5 text-xs text-slate-400">
            <div className="mb-2 font-semibold uppercase tracking-wider text-slate-500">How it works</div>
            <ol className="list-decimal space-y-1 pl-4">
              <li>Intake classifies the channel & extracts links/entities.</li>
              <li>Cheap triage assigns a preliminary risk score.</li>
              <li>High-risk / high-value cases escalate to deep analysis (render + LLM).</li>
              <li>Trust engine fuses evidence into one verdict + action.</li>
            </ol>
          </div>
        </div>

        {/* Right — results */}
        <div className="space-y-6">
          {!result && !loading && !error && (
            <div className="card flex h-full min-h-[300px] flex-col items-center justify-center p-10 text-center text-slate-500">
              <div className="mb-3 text-4xl">🔎</div>
              <p className="max-w-sm text-sm">
                Paste a suspicious email, URL, or social post — or upload a voice clip — and hit
                <span className="text-slate-300"> Analyze</span>. Or try a demo scenario.
              </p>
            </div>
          )}

          {loading && (
            <div className="card flex min-h-[300px] flex-col items-center justify-center p-10 text-center">
              <div className="mb-4 flex gap-1.5">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="h-3 w-3 animate-pulseline rounded-full bg-sky-400" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
              <p className="text-sm text-slate-400">Running trust pipeline — triage, rendering & reasoning…</p>
            </div>
          )}

          {error && (
            <div className="card border-rose-500/40 p-5 text-sm text-rose-300">
              <div className="font-semibold">Analysis failed</div>
              <p className="mt-1 text-rose-400/80">{error}</p>
              <p className="mt-2 text-xs text-slate-500">Is the backend running on {process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000"}?</p>
            </div>
          )}

          {result && (
            <>
              {/* Verdict banner */}
              <div className={`card p-6 ring-1 ${s.ring}`}>
                <div className="flex flex-col items-center gap-6 sm:flex-row">
                  <RiskGauge score={result.risk_score} level={result.risk_level} />
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <LevelChip level={result.risk_level} />
                      <span className="chip !text-[10px] uppercase">{result.channel_type}</span>
                      {result.escalated && <span className="chip !text-[10px] text-indigo-300">deep analysis</span>}
                    </div>
                    <h2 className={`text-xl font-bold ${s.text}`}>{result.threat_label}</h2>
                    <p className="mt-1 text-sm text-slate-300">{result.summary}</p>
                    <div className="mt-3 max-w-xs">
                      <Bar value={result.confidence} label="Confidence" />
                    </div>
                  </div>
                </div>

                <div className={`mt-5 rounded-xl border p-4 ${s.bg} border-edge`}>
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Recommended action</div>
                  <p className="mt-1 text-sm text-slate-100">{result.recommended_action}</p>
                </div>
              </div>

              {/* Entities & links */}
              {(result.entities?.length > 0 || result.links?.length > 0) && (
                <div className="card p-5">
                  {result.entities?.length > 0 && (
                    <div className="mb-3">
                      <div className="mb-1.5 text-xs uppercase tracking-wider text-slate-500">Detected entities</div>
                      <div className="flex flex-wrap gap-2">
                        {result.entities.map((e, i) => (
                          <span key={i} className="chip">
                            {e.text}
                            <span className="text-slate-500">· {e.type}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {result.links?.length > 0 && (
                    <div>
                      <div className="mb-1.5 text-xs uppercase tracking-wider text-slate-500">Links</div>
                      <div className="space-y-1.5">
                        {result.links.map((l, i) => (
                          <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
                            <span className={`h-1.5 w-1.5 rounded-full ${l.allowlisted ? "bg-emerald-400" : l.suspicious ? "bg-rose-400" : "bg-slate-500"}`} />
                            <span className="break-all font-mono text-xs text-slate-300">{l.raw}</span>
                            {l.allowlisted && <span className="chip !text-[10px] text-emerald-300">official</span>}
                            {l.suspicious && <span className="chip !text-[10px] text-rose-300">{l.reasons?.[0] || "suspicious"}</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
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

      <footer className="mt-10 border-t border-edge pt-4 text-center text-xs text-slate-600">
        TrustShield MVP · prototype for SEBI PS1 · not production infrastructure. Verdicts are advisory.
      </footer>
    </main>
  );
}
