// TrustShield extension — content script.
// Injects a shield badge + inline verdict panel into Gmail / Outlook / WhatsApp Web.
// All API calls go through the background service worker to bypass CORS.

(function () {
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
    if (p === "gmail") { const c = document.querySelector("div[role='main']"); return c ? c.innerText.slice(0, 8000) : ""; }
    if (p === "outlook") { const c = document.querySelector("[role='main'], div[data-testid='message-view-body-content']"); return c ? c.innerText.slice(0, 8000) : ""; }
    if (p === "whatsapp") { const c = document.querySelector("#main"); return c ? c.innerText.slice(0, 8000) : ""; }
    return "";
  }

  function esc(s) { return String(s || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  var panel = null;
  var btn = null;

  function makePanel() {
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = "tshield-panel";
    panel.style.cssText = [
      "display:none", "position:fixed", "z-index:99998", "right:16px", "top:66px",
      "width:340px", "max-height:480px", "overflow-y:auto",
      "background:#fff", "border-radius:12px", "border:1px solid #e2e8f0",
      "box-shadow:0 8px 32px rgba(0,0,0,.15)", "padding:16px",
      "font:13px/1.5 system-ui,-apple-system,sans-serif", "color:#1e293b",
    ].join(";");
    panel.innerHTML = '<div style="font-size:12px;color:#94a3b8;text-align:center;padding:12px 0;">Select an email or message, then click 🛡️ TrustShield</div>';
    document.body.appendChild(panel);
    return panel;
  }

  function makeBtn() {
    if (btn) return btn;
    btn = document.createElement("div");
    btn.id = "tshield-btn";
    btn.innerHTML = (
      '<div style="display:flex;align-items:center;gap:7px;height:100%;padding:0 12px;">' +
      '<span style="font-size:18px;line-height:1;">🛡️</span>' +
      '<span style="font-weight:700;font-size:12px;letter-spacing:.3px;white-space:nowrap;">TrustShield</span>' +
      '</div>'
    );
    btn.style.cssText = [
      "position:fixed", "z-index:99999", "right:16px", "top:16px",
      "height:40px", "border-radius:10px", "display:flex", "align-items:center",
      "background:#0f4c81", "color:#fff", "font-family:system-ui,-apple-system,sans-serif",
      "cursor:pointer", "box-shadow:0 2px 12px rgba(0,0,0,.3)", "transition:transform .15s",
      "user-select:none",
    ].join(";");
    btn.addEventListener("mouseenter", function () { btn.style.transform = "scale(1.05)"; });
    btn.addEventListener("mouseleave", function () { btn.style.transform = "scale(1)"; });
    document.body.appendChild(btn);
    return btn;
  }

  function showChecking() {
    var p = makePanel();
    p.innerHTML = '<div style="text-align:center;padding:20px 0;">' +
      '<div style="width:32px;height:32px;border:3px solid #e2e8f0;border-top-color:#0ea5e9;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 10px;"></div>' +
      '<div style="font-size:13px;font-weight:600;color:#475569;">Analyzing…</div></div>' +
      '<style>@keyframes spin{to{transform:rotate(360deg)}}</style>';
    p.style.display = "block";
  }

  function showResult(result) {
    var p = makePanel();
    var lvl = result.risk_level || "low";
    var colors = {
      low:    { bg: "#f0fdf4", bd: "#bbf7d0", text: "#16a34a", dot: "#22c55e", label: "LOW RISK · VERIFIED" },
      medium: { bg: "#fffbeb", bd: "#fde68a", text: "#d97706", dot: "#f59e0b", label: "SUSPICIOUS · REVIEW" },
      high:   { bg: "#fef2f2", bd: "#fecaca", text: "#dc2626", dot: "#ef4444", label: "HIGH RISK · LIKELY THREAT" },
    };
    var c = colors[lvl] || colors.low;
    p.innerHTML =
      '<div style="border:1px solid ' + c.bd + ';border-radius:10px;padding:14px;background:' + c.bg + ';margin-bottom:12px;">' +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">' +
      '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + c.dot + ';"></span>' +
      '<span style="font-size:11px;font-weight:700;text-transform:uppercase;color:' + c.text + ';letter-spacing:.5px;">' + c.label + '</span></div>' +
      '<div style="font-size:28px;font-weight:800;color:' + c.text + ';line-height:1;">' + (result.risk_score ?? "–") + '<span style="font-size:14px;font-weight:500;">/100</span></div>' +
      '<div style="font-size:13px;font-weight:700;color:#1e293b;margin-top:6px;">' + esc(result.threat_label || "") + '</div>' +
      '<div style="font-size:11px;color:#64748b;margin-top:6px;line-height:1.5;">' + esc((result.summary || "").slice(0, 250)) + '</div>' +
      '</div>' +
      '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;margin-bottom:8px;">' +
      '<div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">What to do</div>' +
      '<div style="font-size:11px;color:#334155;line-height:1.5;">' + esc(result.recommended_action || "") + '</div>' +
      '</div>' +
      '<div style="font-size:10px;color:#94a3b8;text-align:right;">TrustShield · ' + esc((result.id || "").slice(0, 8)) + '</div>';
    p.style.display = "block";
  }

  function showError(err) {
    var p = makePanel();
    p.innerHTML = '<div style="color:#dc2626;font-size:12px;padding:8px;">Analysis failed: ' + esc(err) + '</div>';
    p.style.display = "block";
  }

  function handleClick() {
    var p = makePanel();
    p.innerHTML = ""; // Clear old content first
    if (p.style.display === "block") { p.style.display = "none"; return; }

    var text = getEmailText();
    if (!text || text.length < 10) {
      p.innerHTML = '<div style="font-size:12px;color:#94a3b8;text-align:center;padding:12px 0;">Open an email or message first, then click 🛡️ TrustShield</div>';
      p.style.display = "block";
      return;
    }

    showChecking();

    try {
      chrome.runtime.sendMessage({ type: "tshield:analyze", text: text }, function (resp) {
        if (chrome.runtime.lastError) { showError(chrome.runtime.lastError.message); return; }
        if (!resp || resp.error) { showError((resp && resp.error) || "No response"); }
        else { showResult(resp.result); chrome.runtime.sendMessage({ type: "tshield:result", result: resp.result }); }
      });
    } catch (e) { showError(String(e)); }
  }

  // Close panel when clicking outside
  document.addEventListener("click", function (e) {
    if (!btn || !panel) return;
    if (!btn.contains(e.target) && !panel.contains(e.target)) panel.style.display = "none";
  }, true);

  // Inject
  function inject() {
    var b = makeBtn();
    makePanel();
    b.removeEventListener("click", handleClick);
    b.addEventListener("click", handleClick);
  }

  inject();
  // Re-inject after SPA navigation (Gmail/Outlook are single-page apps)
  var obs = new MutationObserver(function () { inject(); });
  obs.observe(document.body, { childList: true, subtree: true });
})();
