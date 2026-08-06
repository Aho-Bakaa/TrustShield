// TrustShield extension — content script.
// Injects a floating "Check with TrustShield" button into Gmail / Outlook /
// WhatsApp Web. The content script cannot call localhost directly (CORS)
// so it delegates the fetch to the background service worker which has no
// origin restrictions.

// ---- Platform detection ----
function platform() {
  const h = window.location.hostname;
  if (h.includes("mail.google.com")) return "gmail";
  if (h.includes("outlook")) return "outlook";
  if (h.includes("whatsapp.com")) return "whatsapp";
  return "unknown";
}

function getEmailText() {
  const p = platform();
  if (p === "gmail") {
    const container = document.querySelector("div[role='main']");
    return container ? container.innerText.slice(0, 8000) : "";
  }
  if (p === "outlook") {
    const container = document.querySelector("[role='main'], div[data-testid='message-view-body-content']");
    return container ? container.innerText.slice(0, 8000) : "";
  }
  if (p === "whatsapp") {
    const pane = document.querySelector("#main");
    return pane ? pane.innerText.slice(0, 8000) : "";
  }
  return "";
}

function injectButton() {
  if (document.getElementById("tshield-btn")) return;

  const btn = document.createElement("button");
  btn.id = "tshield-btn";
  btn.textContent = "Check with TrustShield";
  btn.style.cssText = [
    "position:fixed", "z-index:99999", "right:20px", "top:20px",
    "padding:10px 14px", "border:none", "border-radius:8px",
    "background:#0f4c81", "color:#fff", "font:600 13px/1 system-ui",
    "cursor:pointer", "box-shadow:0 2px 8px rgba(0,0,0,.25)",
  ].join(";");

  btn.addEventListener("click", () => {
    const text = getEmailText();
    if (!text || text.length < 10) {
      alert("TrustShield: no message text found on this page. Open an email/message first.");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Analyzing…";
    // Delegate to background worker — no CORS restrictions there.
    chrome.runtime.sendMessage({ type: "tshield:analyze", text }, (resp) => {
      btn.disabled = false;
      btn.textContent = "Check with TrustShield";
      if (!resp || resp.error) {
        chrome.runtime.sendMessage({ type: "tshield:error", error: resp?.error || "Unknown error" });
      } else {
        chrome.runtime.sendMessage({ type: "tshield:result", result: resp.result });
      }
    });
  });

  document.body.appendChild(btn);
}

// Re-inject after SPA navigation (Gmail/Outlook are single-page apps).
injectButton();
const observer = new MutationObserver(() => injectButton());
observer.observe(document.body, { childList: true, subtree: true });
