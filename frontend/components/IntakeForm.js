"use client";
import { useEffect, useRef, useState } from "react";
import { analyzeAudio, analyzeImage, analyzeText } from "@/lib/api";
import { SAMPLES } from "@/lib/samples";
import { IconFileText, IconVolume2, IconImage, IconShield, IconSparkles } from "./ui";

const MODES = [
  { key: "text", label: "Text / Post / URL", icon: IconFileText },
  { key: "audio", label: "Audio Spoof", icon: IconVolume2 },
  { key: "image", label: "Image / PDF", icon: IconImage },
];

const ACCEPT = {
  audio: ".wav,.flac,.ogg,.mp3,.m4a,.aac,.opus",
  image: ".png,.jpg,.jpeg,.webp,.gif,.bmp,.pdf,.eml",
};

export default function IntakeForm({ onStart, onResult, onError }) {
  const [mode, setMode] = useState("text");
  const [text, setText] = useState("");
  const [claimed, setClaimed] = useState("");
  const [hint, setHint] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  // Refs so the global paste handler always sees the latest values.
  const refs = useRef({});
  refs.current = { mode, text, claimed, hint, busy };

  function loadSample(s) {
    setMode("text");
    setFile(null);
    setText(s.raw_input);
    setClaimed(s.claimed_source || "");
    setHint(s.channel_hint || "");
  }

  async function runAnalyze({ mode: m, file: fl }) {
    const { text: t, claimed: c, hint: h } = refs.current;
    setBusy(true);
    onStart?.();
    try {
      let res;
      if (m === "audio") {
        if (!fl) throw new Error("Please select or drop an audio file first.");
        res = await analyzeAudio({ file: fl, claimed_source: c, context: t });
      } else if (m === "image") {
        if (!fl) throw new Error("Please select, drop or paste an image/PDF first.");
        res = await analyzeImage({ file: fl, claimed_source: c, context: t });
      } else {
        if (!t.trim()) throw new Error("Please input a message, URL, or social post to analyze.");
        res = await analyzeText({ raw_input: t, claimed_source: c || undefined, channel_hint: h || undefined });
      }
      onResult?.(res);
    } catch (e) {
      onError?.(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  // Paste a screenshot from the clipboard anywhere -> auto-analyze.
  useEffect(() => {
    function onPaste(e) {
      const items = e.clipboardData?.items || [];
      for (const it of items) {
        if (it.kind === "file" && (it.type.startsWith("image/") || it.type === "application/pdf")) {
          const blob = it.getAsFile();
          if (blob && !refs.current.busy) {
            const ext = it.type === "application/pdf" ? "pdf" : (it.type.split("/")[1] || "png");
            const f = new File([blob], `pasted.${ext}`, { type: blob.type });
            setMode("image");
            setFile(f);
            runAnalyze({ mode: "image", file: f });
            e.preventDefault();
          }
          return;
        }
      }
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pickFile(f) {
    if (!f) return;
    const isAudio = f.type.startsWith("audio/");
    setMode(isAudio ? "audio" : "image");
    setFile(f);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  const isUpload = mode === "audio" || mode === "image";

  return (
    <div className="card overflow-hidden p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-slate-200 pb-3">
        <IconShield className="h-4.5 w-4.5 text-sebiTeal" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-650">
          Intake Scan Controller
        </h3>
      </div>

      {/* Tabs */}
      <div className="mb-5 flex rounded-xl bg-slate-100 p-1 border border-slate-200">
        {MODES.map((m) => {
          const Icon = m.icon;
          const isActive = mode === m.key;
          return (
            <button
              key={m.key}
              className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs font-bold transition-all duration-200 ${
                isActive 
                  ? "bg-white text-sebiNavy shadow-sm border border-slate-200" 
                  : "text-slate-500 hover:text-slate-800"
              }`}
              onClick={() => { setMode(m.key); setFile(null); }}
            >
              <Icon className={`h-4 w-4 ${isActive ? "text-sebiNavy" : "text-slate-400"}`} />
              <span>{m.label}</span>
            </button>
          );
        })}
      </div>

      {/* Form Content */}
      {mode === "text" ? (
        <div className="space-y-1.5">
          <label className="block text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Source Raw Input Text / URL
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={7}
            placeholder="Paste raw email body, message details, official URLs, or social-media posts. You can also paste screenshots directly using Ctrl+V."
            className="w-full resize-none rounded-xl border border-slate-250 bg-white px-3.5 py-3 text-xs text-slate-800 outline-none focus:border-sebiNavy/50 focus:ring-1 focus:ring-sebiNavy/20 placeholder-slate-400 transition-all font-mono"
          />
        </div>
      ) : (
        <div className="space-y-4">
          <div
            className={`flex flex-col items-center justify-center gap-3.5 rounded-xl border border-dashed px-4 py-8 text-center cursor-pointer transition-all duration-200 ${
              dragOver 
                ? "border-sebiNavy bg-sky-50 shadow-[0_0_12px_rgba(27,104,179,0.08)]" 
                : "border-slate-300 bg-slate-50/50 hover:border-slate-400"
            }`}
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            role="button"
          >
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT[mode]}
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white border border-slate-200 text-sebiTeal shadow-sm">
              {mode === "image" ? <IconImage className="h-6 w-6" /> : <IconVolume2 className="h-6 w-6" />}
            </div>

            <div className="space-y-1">
              <div className="text-xs font-bold text-slate-700">
                {file ? file.name : `Drag & drop your ${mode === "image" ? "image/PDF" : "audio clip"} here`}
              </div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                {file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : `or click to browse local files`}
              </div>
            </div>
            
            <div className="text-[10px] text-slate-500 font-mono">
              {mode === "image" ? "Supported: PNG · JPG · WEBP · PDF · EML" : "Supported: WAV · FLAC · OGG · MP3 · M4A"}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-[10px] uppercase font-bold tracking-wider text-slate-500">
              Additional Context (Optional)
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              rows={2}
              placeholder={mode === "image" ? "Provide any text context, expected sender, or details about the image..." : "Provide caller identity details or claims made in the recording..."}
              className="w-full resize-none rounded-xl border border-slate-250 bg-white px-3.5 py-3 text-xs text-slate-800 outline-none focus:border-sebiNavy/50 focus:ring-1 focus:ring-sebiNavy/20 placeholder-slate-400 transition-all font-mono"
            />
          </div>
        </div>
      )}

      {/* Input Parameters */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label className="block text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Claimed Identity Source
          </label>
          <input
            value={claimed}
            onChange={(e) => setClaimed(e.target.value)}
            placeholder="e.g. SEBI, Zerodha, NSE"
            className="w-full rounded-xl border border-slate-250 bg-white px-3.5 py-2.5 text-xs text-slate-855 outline-none focus:border-sebiNavy/50 transition-all font-bold"
          />
        </div>
        {mode === "text" && (
          <div className="space-y-1.5">
            <label className="block text-[10px] uppercase font-bold tracking-wider text-slate-500">
              Communication Channel
            </label>
            <div className="relative">
              <select
                value={hint}
                onChange={(e) => setHint(e.target.value)}
                className="w-full appearance-none rounded-xl border border-slate-250 bg-white px-3.5 py-2.5 text-xs text-slate-800 outline-none focus:border-sebiNavy/50 transition-all font-bold"
              >
                <option value="">Auto-Detect Mode</option>
                <option value="email">Email Notification</option>
                <option value="url">Direct Website Link</option>
                <option value="social">Social Media Feed</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Scan Button */}
      <button 
        className="mt-5 rounded-lg bg-sebiNavy hover:bg-sebiNavy/90 text-white font-semibold text-sm px-6 py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" 
        onClick={() => runAnalyze({ mode, file })} 
        disabled={busy}
      >
        {busy ? "Analyzing..." : "Scan"}
      </button>

      {/* Demo cases */}
      <div className="mt-5 border-t border-slate-200 pt-4">
        <div className="mb-2.5 flex items-center gap-1.5">
          <IconSparkles className="h-3.5 w-3.5 text-amber-500" />
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">System Verification Test Cases</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <button 
              key={s.key} 
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-250 hover:border-slate-350 px-2.5 py-1.5 text-[10px] font-bold text-slate-655 hover:text-slate-800 transition-all duration-200" 
              onClick={() => loadSample(s)}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-sebiTeal" />
              {s.title}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
