"use client";
import { useState, useEffect } from "react";
import IntakeForm from "@/components/IntakeForm";
import EvidenceList from "@/components/EvidenceList";
import TracePanel from "@/components/TracePanel";
import { LevelChip, RiskGauge, Bar, LEVEL_STYLES, IconChevron } from "@/components/ui";
import VoicePanel from "@/components/VoicePanel";
import { getHealth, createShare } from "@/lib/api";

const PHASES = ["Classifying input type", "Analyzing content", "Rendering linked pages", "Verifying claims across web", "Producing verdict"];

// One clear action per risk level (roadmap 1.2 — "What should I do?").
const ACTION_FOR = {
  high: { label: "Report & Delete", tone: "bg-rose-600 hover:bg-rose-700" },
  medium: { label: "Verify Independently", tone: "bg-amber-600 hover:bg-amber-700" },
  low: { label: "Ignore — Looks Genuine", tone: "bg-emerald-600 hover:bg-emerald-700" },
};

function buildScoresSummary(result) {
  const entities = result.entities?.map(e => e.text).join(", ") || "Unknown";
  const links = result.links?.map(l => l.raw).join("; ") || "None";
  const imp = result.detectors?.[0]?.fields?.impersonated_entity || entities;
  return (
    `TrustShield analysis — suspected ${result.threat_label}\n\n` +
    `Risk: ${result.risk_score}/100 (${result.risk_level})\n` +
    `Impersonated entity: ${imp}\n` +
    `Involved entity/entities: ${entities}\n` +
    `Links in message: ${links}\n\n` +
    `Summary: ${result.summary}\n\n` +
    `Recommended action: ${result.recommended_action}\n\n` +
    `Analysis ID: ${result.id}`
  );
}

function ScoresReportButton({ result }) {
  const [copied, setCopied] = useState(false);
  async function handleReport() {
    const summary = buildScoresSummary(result);
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      /* clipboard unavailable — still open the portal */
    }
    window.open("https://scores.sebi.gov.in/", "_blank", "noopener,noreferrer");
  }
  return (
    <button
      onClick={handleReport}
      className="shrink-0 rounded-lg border border-sebiTeal/40 bg-sebiTeal/10 px-4 py-2.5 text-xs font-bold text-sebiNavy hover:bg-sebiTeal/20 transition-colors"
      title="Opens the SEBI SCORES portal and copies a pre-filled complaint summary to the clipboard"
    >
      {copied ? "Complaint summary copied!" : "Report to SEBI SCORES"}
    </button>
  );
}

function VerdictHeader({ result, onShare }) {
  const s = LEVEL_STYLES[result.risk_level];
  const action = ACTION_FOR[result.risk_level] || ACTION_FOR.low;

  return (
    <div className={`rounded-2xl border bg-white p-8 ${s ? s.ring : ""}`}>
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <RiskGauge score={result.risk_score} level={result.risk_level} />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <LevelChip level={result.risk_level} />
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-500">
              {result.channel_type}
            </span>
          </div>
          <h2 className={`text-lg font-extrabold tracking-tight ${s ? s.text : "text-slate-800"}`}>{result.threat_label}</h2>
          <p className="text-sm leading-relaxed text-slate-600">{result.summary}</p>
          <div className="max-w-xs"><Bar value={result.confidence} label="Confidence" /></div>
        </div>
      </div>

      {/* "What should I do?" — one clear action */}
      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className={`flex-1 rounded-xl border border-slate-200 p-4 ${s ? s.bg : ""}`}>
          <p className="text-xs font-bold text-slate-700">{result.recommended_action}</p>
        </div>
        <button
          onClick={onShare}
          className="shrink-0 rounded-lg bg-white border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors"
          title="Copy a shareable link to this verdict"
        >
          Share
        </button>
        {result.risk_level === "high" && <ScoresReportButton result={result} />}
        <button className={`shrink-0 rounded-lg px-5 py-2.5 text-xs font-bold text-white transition-colors ${action.tone}`}>
          {action.label}
        </button>
      </div>
    </div>
  );
}

function DetailsSection({ result, hasLinks, hasEntities }) {
  const [open, setOpen] = useState(true);
  const searchEvidence = result.evidence?.filter(e => e.source === "search") || [];
  const mainEvidence = result.evidence?.filter(e => e.source !== "search") || [];

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-6 py-4 text-left hover:bg-slate-50 transition-colors"
      >
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">See how we determined this</h3>
        <IconChevron className={`h-4 w-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="space-y-6 border-t border-slate-200 p-6">
          <VoicePanel fields={result.detectors?.[0]?.fields} />
          <EvidenceList evidence={mainEvidence} />

          {searchEvidence.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6">
              <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Web Search Verification</h3>
              <div className="space-y-2">
                {searchEvidence.map((e, i) => (
                  <div key={i} className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                      e.label === "Claim verified" ? "bg-emerald-500"
                        : e.label === "Claim contradicted" || e.label === "Claim CONTRADICTED" ? "bg-rose-500"
                        : "bg-slate-400"
                    }`} />
                    <span className="text-slate-700">{e.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

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
        </div>
      )}
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
  const [copied, setCopied] = useState(false);

  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth({ status: "down" })); }, []);
  useEffect(() => {
    if (!loading) { setPhase(0); setStartedAt(null); return; }
    setStartedAt(Date.now());
    const interval = setInterval(() => setPhase(p => p < PHASES.length - 1 ? p + 1 : p), 4000);
    return () => clearInterval(interval);
  }, [loading]);

  async function handleShare() {
    if (!result) return;
    try {
      const { token } = await createShare(result.id);
      const shareUrl = `${window.location.origin}/share/${token}`;
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy this share link:", `${window.location.origin}/share/${result.id}`);
    }
  }

  const hasLinks = result?.links?.length > 0;
  const hasEntities = result?.entities?.length > 0;

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <div className="mb-10">
        <h1 className="text-2xl font-extrabold tracking-tight text-sebiNavy">TrustShield Scanner</h1>
        <p className="mt-2 text-sm text-slate-500">
          Paste a message, URL, screenshot, or upload audio. The system auto-detects the input, verifies claims across the web, and produces a verdict.
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
            <VerdictHeader result={result} onShare={handleShare} />
            {copied && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-bold text-emerald-700">
                Share link copied to clipboard.
              </div>
            )}
            <DetailsSection result={result} hasLinks={hasLinks} hasEntities={hasEntities} />
          </>
        )}
      </div>
    </main>
  );
}
