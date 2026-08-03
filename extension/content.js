// TrustShield extension — content script.
// Injects a "Check with TrustShield" button into Gmail / Outlook / WhatsApp Web
// that grabs the current email/message text and sends it to the backend API.
// The selected email thread's body is read from the DOM (best-effort per platform).

const API_BASE = "http://127.0.0.1:8000";

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
    // Gmail: the open message body is in the message container; grab visible text.
    const container = document.querySelector("div[role='main']");
    return container ? container.innerText.slice(0, 8000) : "";
  }
  if (p === "outlook") {
    const container = document.querySelector("[role='main'], div[data-testid='message-view-body-content']");
    return container ? container.innerText.slice(0, 8000) : "";
  }
  if (p === "whatsapp") {
    // WhatsApp Web: the currently selected chat pane text.
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
    "position:fixed", "z-index:99999", "right:20px", "bottom:20px",
    "padding:10px 14px", "border:none", "border-radius:8px",
    "background:#0f4c81", "color:#fff", "font:600 13px/1 system-ui",
    "cursor:pointer", "box-shadow:0 2px 8px rgba(0,0,0,.25)",
  ].join(";");

  btn.addEventListener("click", async () => {
    const text = getEmailText();
    if (!text || text.length < 10) {
      alert("TrustShield: no message text found on this page. Open an email/message first.");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Analyzing…";
    try {
      const res = await fetch(`${API_BASE}/api/analyze/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: text }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      chrome.runtime.sendMessage({ type: "tshield:result", result: data });
    } catch (err) {
      chrome.runtime.sendMessage({ type: "tshield:error", error: String(err) });
    } finally {
      btn.disabled = false;
      btn.textContent = "Check with TrustShield";
    }
  });

  document.body.appendChild(btn);
}

// Re-inject after SPA navigation (Gmail/Outlook are single-page apps).
injectButton();
const observer = new MutationObserver(() => injectButton());
observer.observe(document.body, { childList: true, subtree: true });
