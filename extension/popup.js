// TrustShield extension — popup script.
// Reads the latest stored verdict and renders it in a polished card.

chrome.storage.local.get(["lastResult", "lastError"], ({ lastResult, lastError }) => {
  const empty = document.getElementById("empty");
  const resultDiv = document.getElementById("result");

  if (lastError) {
    empty.style.display = "none";
    resultDiv.innerHTML = `<div style="color:#dc2626;font-size:12px;padding:8px;">Last check failed: ${escapeHtml(lastError)}</div>`;
    return;
  }
  if (!lastResult) {
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";

  const lvl = lastResult.risk_level || "low";
  resultDiv.innerHTML = `
    <div class="verdict ${lvl}">
      <div class="level-row">
        <span class="dot ${lvl}"></span>
        <span class="badge ${lvl}">${lvl === "low" ? "LOW RISK / VERIFIED" : lvl === "medium" ? "SUSPICIOUS / REVIEW" : "HIGH RISK / LIKELY THREAT"}</span>
      </div>
      <div class="risk ${lvl}">${lastResult.risk_score ?? "–"}<small>/100</small></div>
      <div class="label">${escapeHtml(lastResult.threat_label || "")}</div>
      <div class="summary">${escapeHtml((lastResult.summary || "").slice(0, 200))}</div>
    </div>
    <div class="action">
      <h3>What to do</h3>
      <p>${escapeHtml(lastResult.recommended_action || "")}</p>
    </div>
    <div class="muted" style="text-align:right;">Analysis ID: ${escapeHtml(lastResult.id || "").slice(0, 12)}</div>
  `;
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
