// One-click demo inputs mapped to the four PS1 scenarios.
// Phishing/social samples link to LOCAL FIXTURE pages served by the backend so
// Playwright genuinely renders a page and detects credential/payment capture —
// no reliance on live malicious sites.
const API = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const FX = `${API}/fixtures`;

export const SAMPLES = [
  {
    key: "phishing",
    title: "Phishing email (SEBI KYC page)",
    channel_hint: "email",
    claimed_source: "SEBI",
    raw_input:
      `Subject: URGENT: Your SEBI investor account will be suspended\n\nDear Investor, SEBI has detected irregular trading in your demat account. To avoid immediate suspension, re-verify your KYC and OTP within 24 hours here: ${FX}/fake-sebi-kyc.html\n\nFailure to act will freeze your holdings.\n- SEBI Compliance Team`,
  },
  {
    key: "broker",
    title: "Broker login phishing (rendered)",
    channel_hint: "email",
    claimed_source: "Zerodha",
    raw_input:
      `Your Kite account is temporarily blocked due to failed KYC. Reactivate immediately here: ${FX}/fake-zerodha-login.html to restore access before it is deactivated.`,
  },
  {
    key: "social",
    title: "Social manipulation (advisory page)",
    channel_hint: "social",
    claimed_source: "",
    raw_input:
      `🚀 URGENT BUY CALL 🚀 Insider tip: guaranteed 200% returns, SEBI-registered advisor. Join our VIP channel before it's too late: ${FX}/fake-advisory.html`,
  },
  {
    key: "ipo",
    title: "Pre-IPO payment scam (URL)",
    channel_hint: "url",
    claimed_source: "NSE",
    raw_input: `${FX}/fake-ipo-payment.html`,
  },
  {
    key: "verified",
    title: "Verified official communication",
    channel_hint: "email",
    claimed_source: "SEBI",
    raw_input:
      "Subject: SEBI Investor Charter update\n\nThe updated Investor Charter is published on our website. Read it at https://www.sebi.gov.in/investor-charter.html . SEBI communicates only through official channels and never asks for OTP or payment. dkim=pass spf=pass",
  },
];
