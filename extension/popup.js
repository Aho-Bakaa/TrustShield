// TrustShield extension — popup script.
// Shows the last verdict stored by the background worker.

chrome.storage.local.get(["lastResult", "lastError"], ({ lastResult, lastError }) => {
  const status = document.getElementById("status");
  const resultDiv = document.getElementById("result");

  if (lastError) {
    status.textContent = "Last check failed: " + lastError;
    return;
  }
  if (!lastResult) {
    status.textContent = "No checks yet. Open an email/message and click the floating “Check with TrustShield” button.";
    return;
  }

  status.style.display = "none";
  resultDiv.style.display = "block";

  const level = lastResult.risk_level || "low";
  resultDiv.innerHTML = `
    <div class="chip ${level}">${level.toUpperCase()}</div>
    <div class="score">${lastResult.risk_score ?? "–"}/100</div>
    <div class="label">${escapeHtml(lastResult.threat_label || "")}</div>
    <div class="action ${level}">${escapeHtml(lastResult.recommended_action || "")}</div>
    <p class="muted">${escapeHtml((lastResult.summary || "").slice(0, 200))}</p>
  `;
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
