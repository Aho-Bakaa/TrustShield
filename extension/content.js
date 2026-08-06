// TrustShield extension — content script.
// Injects a small TrustShield badge into Gmail / Outlook / WhatsApp Web.
// Clicking the badge opens an inline mini result panel with the verdict.
// All API calls go through the background service worker to bypass CORS.

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

  const btn = document.createElement("div");
  btn.id = "tshield-btn";
  btn.innerHTML = '<span style="font-size:16px;line-height:1;">🛡️</span>';
  btn.style.cssText = [
    "position:fixed", "z-index:99999", "right:16px", "top:16px",
    "width:40px", "height:40px", "border-radius:10px",
    "background:#0f4c81", "display:flex", "align-items:center",
    "justify-content:center", "cursor:pointer",
    "box-shadow:0 2px 12px rgba(0,0,0,.3)", "transition:all .15s",
  ].join(";");

  const panel = createPanel();

  btn.addEventListener("mouseenter", () => { btn.style.transform = "scale(1.08)"; });
  btn.addEventListener("mouseleave", () => { btn.style.transform = "scale(1)"; });
  btn.addEventListener("click", () => {
    panel.style.display = panel.style.display === "block" ? "none" : "block";
  });

  document.body.appendChild(btn);
  document.body.appendChild(panel);
}

function createPanel() {
  const panel = document.createElement("div");
  panel.id = "tshield-panel";
  panel.style.cssText = [
    "display:none", "position:fixed", "z-index:99998", "right:16px", "top:66px",
    "width:340px", "max-height:480px", "overflow-y:auto",
    "background:#fff", "border-radius:12px", "border:1px solid #e2e8f0",
    "box-shadow:0 8px 32px rgba(0,0,0,.15)", "padding:16px",
    "font:13px/1.5 system-ui, sans-serif", "color:#1e293b",
  ].join(";");
  panel.innerHTML = '<div style="font-size:12px;color:#94a3b8;text-align:center;padding:12px 0;">Select an email or message and click 🛡️</div>';
  return panel;
}

function showChecking(panel) {
  panel.innerHTML = `<div style="text-align:center;padding:20px 0;">
    <div style="width:32px;height:32px;border:3px solid #e2e8f0;border-top-color:#0ea5e9;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 10px;"></div>
    <div style="font-size:13px;font-weight:600;color:#475569;">Analyzing…</div>
  </div>
  <style>@keyframes spin { to { transform: rotate(360deg); } }</style>`;
}

function showResult(panel, result) {
  const lvl = result.risk_level || "low";
  const colors = {
    low:    { bg: "#f0fdf4", border: "#bbf7d0", text: "#16a34a", dot: "#22c55e", label: "LOW RISK / VERIFIED" },
    medium: { bg: "#fffbeb", border: "#fde68a", text: "#d97706", dot: "#f59e0b", label: "SUSPICIOUS / REVIEW" },
    high:   { bg: "#fef2f2", border: "#fecaca", text: "#dc2626", dot: "#ef4444", label: "HIGH RISK / LIKELY THREAT" },
  };
  const c = colors[lvl] || colors.low;

  panel.innerHTML = `
    <div style="border:1px solid ${c.border};border-radius:10px;padding:14px;background:${c.bg};margin-bottom:12px;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${c.dot};"></span>
        <span style="font-size:11px;font-weight:700;text-transform:uppercase;color:${c.text};letter-spacing:.5px;">${c.label}</span>
      </div>
      <div style="font-size:26px;font-weight:800;color:${c.text};line-height:1;">${result.risk_score ?? "–"}<span style="font-size:13px;font-weight:500;">/100</span></div>
      <div style="font-size:13px;font-weight:700;color:#1e293b;margin-top:4px;">${escapeHtml(result.threat_label || "")}</div>
      <div style="font-size:11px;color:#64748b;margin-top:6px;line-height:1.4;">${escapeHtml((result.summary || "").slice(0, 200))}</div>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;margin-bottom:8px;">
      <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;">WHAT TO DO</div>
      <div style="font-size:11px;color:#334155;line-height:1.5;">${escapeHtml(result.recommended_action || "")}</div>
    </div>
    <div style="font-size:10px;color:#94a3b8;text-align:right;">Analysis ID: ${escapeHtml(result.id || "").slice(0, 12)}</div>
  `;
}

function showError(panel, err) {
  panel.innerHTML = `<div style="color:#dc2626;font-size:12px;padding:8px;">Analysis failed: ${escapeHtml(err)}</div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---- Click handler ----
document.addEventListener("click", (e) => {
  const btn = document.getElementById("tshield-btn");
  const panel = document.getElementById("tshield-panel");
  if (!btn || !panel) return;
  if (!btn.contains(e.target) && !panel.contains(e.target)) {
    panel.style.display = "none";
  }
});

// Override the initial injectButton to add the click handler.
const origInject = injectButton;
injectButton = function() {
  if (document.getElementById("tshield-btn")) return;
  origInject();
  const btn = document.getElementById("tshield-btn");
  const panel = document.getElementById("tshield-panel");
  btn.addEventListener("click", () => {
    if (panel.style.display === "block") { panel.style.display = "none"; return; }
    const text = getEmailText();
    if (!text || text.length < 10) {
      panel.innerHTML = '<div style="font-size:12px;color:#94a3b8;text-align:center;padding:12px 0;">Open an email or message first, then click 🛡️</div>';
      panel.style.display = "block";
      return;
    }
    panel.style.display = "block";
    showChecking(panel);
    chrome.runtime.sendMessage({ type: "tshield:analyze", text }, (resp) => {
      if (!resp || resp.error) {
        showError(panel, resp?.error || "Unknown error");
      } else {
        showResult(panel, resp.result);
      }
    });
  });
};

// Re-inject after SPA navigation.
injectButton();
const observer = new MutationObserver(() => injectButton());
observer.observe(document.body, { childList: true, subtree: true });
