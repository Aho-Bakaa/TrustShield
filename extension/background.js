// TrustShield extension — background service worker.
// Handles two message types from the content script:
//   1. "tshield:analyze" — fetches the API and stores the result
//   2. "tshield:result" / "tshield:error" — stored by the popup for display
// No CORS restrictions in the service-worker context, so the fetch to
// localhost always works regardless of the origin the content script runs in.

const API_BASE = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "tshield:analyze") {
    analyzeText(msg.text)
      .then((result) => {
        chrome.storage.local.set({ lastResult: result, lastError: null });
        sendResponse({ result });
      })
      .catch((err) => {
        chrome.storage.local.set({ lastResult: null, lastError: String(err) });
        sendResponse({ error: String(err) });
      });
    return true; // keep the sendResponse channel open for the async reply
  }

  if (msg?.type === "tshield:result") {
    chrome.storage.local.set({ lastResult: msg.result, lastError: null });
    sendResponse({ ok: true });
    return true;
  }

  if (msg?.type === "tshield:error") {
    chrome.storage.local.set({ lastResult: null, lastError: msg.error });
    sendResponse({ ok: true });
    return true;
  }

  sendResponse({ ok: true });
  return true;
});

async function analyzeText(text) {
  const res = await fetch(`${API_BASE}/api/analyze/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_input: text }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
