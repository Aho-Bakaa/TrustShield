"use client";
import { useEffect, useRef, useState } from "react";
import { analyzeAudio, analyzeImage, analyzeText } from "@/lib/api";
import { SAMPLES } from "@/lib/samples";
import { IconImage, IconShield, IconSparkles } from "./ui";

const ACCEPT = ".png,.jpg,.jpeg,.webp,.gif,.bmp,.pdf,.eml,.wav,.flac,.ogg,.mp3,.m4a,.aac,.opus";

function guessFileType(f) {
  if (!f) return null;
  if (f.type.startsWith("audio/")) return "audio";
  if (f.type.startsWith("image/") || f.type === "application/pdf" || f.name.endsWith(".eml")) return "image";
  return "image";
}

export default function IntakeForm({ onStart, onResult, onError }) {
  const [text, setText] = useState("");
  const [claimed, setClaimed] = useState("");
  const [hint, setHint] = useState(""); // optional channel override from samples
  const [file, setFile] = useState(null);
  const [fileType, setFileType] = useState(null); // "audio" | "image"
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  // Refs so the global paste handler always sees the latest values.
  const refs = useRef({});
  refs.current = { text, claimed, busy, hint };

  function loadSample(s) {
    setFile(null);
    setFileType(null);
    setText(s.raw_input);
    setClaimed(s.claimed_source || "");
    setHint(s.channel_hint || "");
  }

  async function runAnalyze() {
    const { text: t, claimed: c, hint: h } = refs.current;
    setBusy(true);
    onStart?.();
    try {
      let res;
      if (fileType === "audio") {
        if (!file) throw new Error("Please select or drop an audio file first.");
        res = await analyzeAudio({ file, claimed_source: c, context: t });
      } else if (fileType === "image") {
        if (!file) throw new Error("Please select, drop or paste an image/PDF first.");
        res = await analyzeImage({ file, claimed_source: c, context: t });
      } else {
        if (!t.trim()) throw new Error("Please paste a message, URL, or screenshot to check.");
        res = await analyzeText({ raw_input: t, claimed_source: c || undefined, channel_hint: h || undefined });
      }
      onResult?.(res);
    } catch (e) {
      onError?.(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  // Paste a screenshot/PDF/audio from the clipboard -> show it for review.
  useEffect(() => {
    function onPaste(e) {
      const items = e.clipboardData?.items || [];
      for (const it of items) {
        if (it.kind === "file") {
          const blob = it.getAsFile();
          if (blob && !refs.current.busy) {
            const ext = blob.type === "application/pdf" ? "pdf" : (blob.type.split("/")[1] || "bin");
            const f = new File([blob], `pasted.${ext}`, { type: blob.type });
            const ft = guessFileType(f);
            if (ft) {
              setFile(f);
              setFileType(ft);
              e.preventDefault();
            }
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
    const ft = guessFileType(f);
    setFile(f);
    setFileType(ft);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  const hasFile = Boolean(file);

  return (
    <div className="card overflow-hidden p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-slate-200 pb-3">
        <IconShield className="h-4.5 w-4.5 text-sebiTeal" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-650">
          Check a communication
        </h3>
      </div>

      {/* Single paste-box: text OR drop/paste image/audio */}
      <div
        className={`relative rounded-xl border transition-all duration-200 ${
          dragOver
            ? "border-sebiNavy bg-sky-50 shadow-[0_0_12px_rgba(27,104,179,0.08)]"
            : "border-slate-250 bg-white focus-within:border-sebiNavy/50 focus-within:ring-1 focus-within:ring-sebiNavy/20"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          placeholder={
            hasFile
              ? `${file.name} attached — add optional context or sender details…`
              : "Paste an email, message, URL, or social post… or drop / Ctrl+V a screenshot, PDF, or audio clip. We auto-detect the type."
          }
          className="w-full resize-none rounded-xl bg-transparent px-3.5 py-3 text-xs text-slate-800 outline-none placeholder-slate-400 transition-all font-mono"
        />

        {hasFile && (
          <div className="flex items-center gap-2 border-t border-slate-200 px-3.5 py-2.5">
            <IconImage className="h-4 w-4 shrink-0 text-sebiTeal" />
            <span className="truncate text-[11px] font-semibold text-slate-700">{file.name}</span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold uppercase text-slate-500">
              {fileType}
            </span>
            <button
              type="button"
              onClick={() => { setFile(null); setFileType(null); }}
              className="ml-auto text-[10px] font-bold text-rose-600 hover:text-rose-800"
            >
              Remove
            </button>
          </div>
        )}

        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] || null)}
        />
      </div>

      {/* Input Parameters */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label className="block text-[10px] uppercase font-bold tracking-wider text-slate-500">
            Claimed Identity Source
          </label>
          <input
            value={claimed}
            onChange={(e) => setClaimed(e.target.value)}
            placeholder="e.g. SEBI, Zerodha, NSE (optional)"
            className="w-full rounded-xl border border-slate-250 bg-white px-3.5 py-2.5 text-xs text-slate-855 outline-none focus:border-sebiNavy/50 transition-all font-bold"
          />
        </div>
        <div className="flex items-end">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="w-full rounded-xl border border-slate-250 bg-slate-50 px-3.5 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Browse files…
          </button>
        </div>
      </div>

      {/* Scan Button */}
      <button
        className="mt-5 rounded-lg bg-sebiNavy hover:bg-sebiNavy/90 text-white font-semibold text-sm px-6 py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        onClick={runAnalyze}
        disabled={busy}
      >
        {busy ? "Checking…" : "Check This"}
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
