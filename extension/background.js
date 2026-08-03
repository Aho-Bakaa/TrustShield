// TrustShield extension — background service worker.
// Receives results from the content script and stores them for the popup.

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "tshield:result") {
    chrome.storage.local.set({ lastResult: msg.result, lastError: null });
  } else if (msg?.type === "tshield:error") {
    chrome.storage.local.set({ lastResult: null, lastError: msg.error });
  }
  sendResponse({ ok: true });
  return true;
});
