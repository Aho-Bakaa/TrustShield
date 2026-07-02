"use client";
import { useEffect, useRef, useState } from "react";
import { analyzeAudio, analyzeImage, analyzeText } from "@/lib/api";
import { SAMPLES } from "@/lib/samples";

const MODES = [
  { key: "text", label: "Text / Email / URL / Social" },
  { key: "audio", label: "Audio clip" },
  { key: "image", label: "Image / PDF" },
];

const ACCEPT = {
  audio: ".wav,.flac,.ogg,.mp3,.m4a,.aac,.opus",
  image: ".png,.jpg,.jpeg,.webp,.gif,.bmp,.pdf",
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
        if (!fl) throw new Error("Choose an audio file first.");
        res = await analyzeAudio({ file: fl, claimed_source: c, context: t });
      } else if (m === "image") {
        if (!fl) throw new Error("Choose an image or PDF first.");
        res = await analyzeImage({ file: fl, claimed_source: c, context: t });
      } else {
        if (!t.trim()) throw new Error("Paste a message, URL, or post first.");
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
    <div className="card p-5">
      <div className="mb-4 flex flex-wrap gap-2">
        {MODES.map((m) => (
          <button
            key={m.key}
            className={`btn ${mode === m.key ? "btn-primary" : "btn-ghost"}`}
            onClick={() => { setMode(m.key); setFile(null); }}
          >
            {m.label}
          </button>
        ))}
      </div>

      {mode === "text" ? (
        <>
          <label className="mb-1 block text-xs uppercase tracking-wider text-slate-400">
            Suspicious content
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={7}
            placeholder="Paste a message / email, a URL, or a social-media post…  (tip: you can also paste a screenshot with Ctrl+V)"
            className="w-full resize-y rounded-xl border border-edge bg-ink px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-sky-500"
          />
        </>
      ) : (
        <div
          className={`flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed bg-ink px-4 py-8 text-center transition ${dragOver ? "border-sky-500 bg-sky-500/5" : "border-edge"}`}
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
          <div className="text-2xl">{mode === "image" ? "🖼️" : "🎧"}</div>
          <div className="text-sm text-slate-300">
            {file
              ? `${file.name}`
              : mode === "image"
              ? "Click, drag & drop, or paste (Ctrl+V) a screenshot / PDF"
              : "Click or drag & drop a voice note / call recording"}
          </div>
          <div className="text-xs text-slate-500">
            {mode === "image" ? "png · jpg · webp · pdf — read by the vision model" : "wav · flac · ogg · mp3 · m4a"}
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            rows={2}
            placeholder={mode === "image" ? "Optional context…" : "Optional context (what the caller claimed)…"}
            className="mt-2 w-full resize-y rounded-lg border border-edge bg-panel px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
          />
        </div>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs uppercase tracking-wider text-slate-400">
            Claimed source (optional)
          </label>
          <input
            value={claimed}
            onChange={(e) => setClaimed(e.target.value)}
            placeholder="e.g. SEBI, NSE, Zerodha, company CEO"
            className="w-full rounded-xl border border-edge bg-ink px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-sky-500"
          />
        </div>
        {mode === "text" && (
          <div>
            <label className="mb-1 block text-xs uppercase tracking-wider text-slate-400">
              Channel (auto-detected)
            </label>
            <select
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              className="w-full rounded-xl border border-edge bg-ink px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-sky-500"
            >
              <option value="">Auto-detect</option>
              <option value="email">Email / message</option>
              <option value="url">URL</option>
              <option value="social">Social post</option>
            </select>
          </div>
        )}
      </div>

      <button className="btn-primary mt-4 w-full" onClick={() => runAnalyze({ mode, file })} disabled={busy}>
        {busy ? "Analyzing…" : isUpload ? `Analyze ${mode === "image" ? "image / PDF" : mode}` : "Analyze with TrustShield"}
      </button>

      <div className="mt-4">
        <div className="mb-2 text-xs uppercase tracking-wider text-slate-500">Try a demo scenario</div>
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <button key={s.key} className="chip hover:border-sky-500/60" onClick={() => loadSample(s)}>
              {s.title}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
