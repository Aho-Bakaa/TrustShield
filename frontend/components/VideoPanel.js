"use client";

export default function VideoPanel({ fields }) {
  if (!fields || (!fields.deepfake_probability && !fields.scores)) return null;

  const { is_deepfake, deepfake_probability, deepfake_type, risk_level,
          models_used, faces_detected, frames_analyzed, duration_seconds, scores } = fields;

  const pct = Math.round((deepfake_probability || 0) * 100);
  const isFake = is_deepfake || pct >= 50;
  const color = isFake ? "text-rose-700" : "text-emerald-700";
  const bg = isFake ? "bg-rose-50 border-rose-200" : "bg-emerald-50 border-emerald-200";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Deepfake Detection</h3>

      <div className={`mb-4 rounded-lg border p-4 ${bg}`}>
        <div className="flex items-center justify-between">
          <span className={`text-lg font-extrabold ${color}`}>
            {isFake ? "⚠️ Deepfake Detected" : "✅ Likely Authentic"}
          </span>
          <span className={`text-2xl font-black ${color}`}>{pct}%</span>
        </div>
        <p className="mt-1 text-xs text-slate-600">
          Type: {deepfake_type || "Unknown"} · Risk: {risk_level?.toUpperCase() || "N/A"}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-slate-400 uppercase tracking-wider">Models</div>
          <div className="mt-1 font-bold text-slate-700">{models_used || "-"}</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-slate-400 uppercase tracking-wider">Faces</div>
          <div className="mt-1 font-bold text-slate-700">{faces_detected || "-"} detected</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-slate-400 uppercase tracking-wider">Frames</div>
          <div className="mt-1 font-bold text-slate-700">{frames_analyzed || "-"} analyzed</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="text-slate-400 uppercase tracking-wider">Duration</div>
          <div className="mt-1 font-bold text-slate-700">{duration_seconds ? `${duration_seconds}s` : "-"}</div>
        </div>
      </div>

      {scores && Object.keys(scores).length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-bold text-slate-500 mb-2">Model Scores</div>
          <div className="space-y-1.5">
            {Object.entries(scores).map(([model, score]) => (
              <div key={model} className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-600 w-28 truncate">{model}</span>
                <div className="flex-1 h-2 rounded-full bg-slate-200">
                  <div
                    className="h-2 rounded-full bg-slate-900"
                    style={{ width: `${Math.round(parseFloat(score) * 100)}%` }}
                  />
                </div>
                <span className="text-xs font-bold text-slate-700 tabular-nums w-10 text-right">
                  {Math.round(parseFloat(score) * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
