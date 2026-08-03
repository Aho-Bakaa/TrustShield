import { resolveShare } from "@/lib/api";
import { LevelChip, RiskGauge, Bar, LEVEL_STYLES } from "@/components/ui";
import EvidenceList from "@/components/EvidenceList";
import VoicePanel from "@/components/VoicePanel";

export const dynamic = "force-dynamic";

export default async function SharePage({ params }) {
  const { token } = params;
  let result = null;
  let error = "";

  try {
    result = await resolveShare(token);
  } catch (e) {
    error = e.message || "Invalid share link";
  }

  if (error) {
    return (
      <main className="mx-auto max-w-xl px-4 py-16 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8">
          <h1 className="text-lg font-extrabold text-rose-700">Share link unavailable</h1>
          <p className="mt-2 text-sm text-rose-800">{error}</p>
          <p className="mt-4 text-xs text-slate-500">Share links expire after 7 days.</p>
        </div>
      </main>
    );
  }

  const s = LEVEL_STYLES[result.risk_level] || LEVEL_STYLES.low;
  const mainEvidence = result.evidence?.filter(e => e.source !== "search") || [];

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold tracking-tight text-sebiNavy">TrustShield Verdict</h1>
        <p className="mt-2 text-sm text-slate-500">
          Shared analysis · expires 7 days after creation
        </p>
      </div>

      <div className={`rounded-2xl border bg-white p-8 ${s.ring}`}>
        <div className="flex flex-col items-center gap-6 sm:flex-row">
          <RiskGauge score={result.risk_score} level={result.risk_level} />
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <LevelChip level={result.risk_level} />
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-500">
                {result.channel_type}
              </span>
            </div>
            <h2 className={`text-lg font-extrabold tracking-tight ${s.text}`}>{result.threat_label}</h2>
            <p className="text-sm leading-relaxed text-slate-600">{result.summary}</p>
            <div className="max-w-xs"><Bar value={result.confidence} label="Confidence" /></div>
          </div>
        </div>
        <div className={`mt-5 rounded-xl border border-slate-200 p-4 ${s.bg}`}>
          <p className="text-xs font-bold text-slate-700">{result.recommended_action}</p>
        </div>
      </div>

      <div className="mt-6">
        <VoicePanel fields={result.detectors?.[0]?.fields} />
        <div className="mt-6">
          <EvidenceList evidence={mainEvidence} />
        </div>
      </div>
    </main>
  );
}
