const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export async function getHealth() {
  const r = await fetch(`${BASE}/health`, { cache: "no-store" });
  if (!r.ok) throw new Error("health failed");
  return r.json();
}

export async function analyzeText({ raw_input, claimed_source, channel_hint }) {
  const r = await fetch(`${BASE}/api/analyze/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_input, claimed_source, channel_hint }),
  });
  if (!r.ok) throw new Error((await r.text()) || "analyze failed");
  return r.json();
}

export async function analyzeAudio({ file, claimed_source, context }) {
  const fd = new FormData();
  fd.append("file", file);
  if (claimed_source) fd.append("claimed_source", claimed_source);
  if (context) fd.append("context", context);
  const r = await fetch(`${BASE}/api/analyze/audio`, { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.text()) || "audio analyze failed");
  return r.json();
}

export async function analyzeImage({ file, claimed_source, context }) {
  const fd = new FormData();
  fd.append("file", file);
  if (claimed_source) fd.append("claimed_source", claimed_source);
  if (context) fd.append("context", context);
  const r = await fetch(`${BASE}/api/analyze/image`, { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.text()) || "image analyze failed");
  return r.json();
}
