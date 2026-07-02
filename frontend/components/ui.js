"use client";

export const LEVEL_STYLES = {
  low: { ring: "ring-emerald-500/40", text: "text-emerald-300", bg: "bg-emerald-500/10", dot: "bg-emerald-400", label: "LOW RISK", grad: "from-emerald-500 to-teal-400" },
  medium: { ring: "ring-amber-500/40", text: "text-amber-300", bg: "bg-amber-500/10", dot: "bg-amber-400", label: "SUSPICIOUS", grad: "from-amber-500 to-orange-400" },
  high: { ring: "ring-rose-500/40", text: "text-rose-300", bg: "bg-rose-500/10", dot: "bg-rose-400", label: "HIGH RISK", grad: "from-rose-500 to-red-500" },
};

const SEV = {
  high: "bg-rose-400",
  medium: "bg-amber-400",
  low: "bg-sky-400",
  info: "bg-slate-500",
};

export function SeverityDot({ severity }) {
  return <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${SEV[severity] || SEV.info}`} />;
}

export function LevelChip({ level }) {
  const s = LEVEL_STYLES[level] || LEVEL_STYLES.low;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${s.bg} ${s.text} ring-1 ${s.ring}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

export function RiskGauge({ score, level }) {
  const s = LEVEL_STYLES[level] || LEVEL_STYLES.low;
  const pct = Math.max(0, Math.min(100, score));
  const deg = (pct / 100) * 360;
  const color = level === "high" ? "#fb7185" : level === "medium" ? "#fbbf24" : "#34d399";
  return (
    <div className="relative h-36 w-36 shrink-0">
      <div
        className="h-full w-full rounded-full"
        style={{ background: `conic-gradient(${color} ${deg}deg, #1e293b ${deg}deg)` }}
      />
      <div className="absolute inset-[10px] flex flex-col items-center justify-center rounded-full bg-panel">
        <div className={`text-4xl font-bold ${s.text}`}>{score}</div>
        <div className="text-[10px] uppercase tracking-widest text-slate-400">/ 100 risk</div>
      </div>
    </div>
  );
}

export function Bar({ value, label }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span className="tabular-nums text-slate-300">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-indigo-400" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
