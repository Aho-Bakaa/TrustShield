"use client";

// Displays voice-detection fields (spoof model, spoof type, classification,
// impersonation target, transcript) for a voice analysis result.
export default function VoicePanel({ fields }) {
  if (!fields) return null;
  const transcript = fields.transcript;
  const spoofModel = fields.spoof_model;
  const spoofType = fields.spoof_type;
  const voiceClass = fields.voice_classification;
  const impTarget = fields.voice_impersonation_target || fields.impersonation_target;
  if (!transcript && !spoofModel && !spoofType) return null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-slate-500">Voice Analysis</h3>
      <div className="space-y-4">
        {spoofModel && (
          <div className="flex flex-wrap gap-2">
            <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-bold text-slate-700">
              Spoof model: {spoofModel}
            </span>
            {spoofType && (
              <span className={`rounded-lg px-2.5 py-1 text-[10px] font-bold ${
                spoofType === "GENUINE" ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-rose-50 text-rose-700 border border-rose-200"
              }`}>
                {spoofType}
              </span>
            )}
          </div>
        )}
        {voiceClass && (
          <div className="text-xs text-slate-600">
            <span className="font-bold text-slate-700">Classification:</span> {voiceClass}
          </div>
        )}
        {impTarget && (
          <div className="text-xs text-slate-600">
            <span className="font-bold text-slate-700">Possible impersonation:</span> {impTarget}
          </div>
        )}
        {transcript && (
          <div>
            <div className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">Transcribed content</div>
            <p className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs leading-relaxed text-slate-700 font-mono">
              {transcript}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
