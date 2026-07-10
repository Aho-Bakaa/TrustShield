"use client";
import Link from "next/link";

export default function Dashboard() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-6">
      <div className="mb-8">
        <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">भारतीय प्रतिभूति और विनिमय बोर्ड</div>
        <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-sebiNavy">TrustShield Verification Portal</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
          A multimodal trust and verification layer for India's securities-market communications. Detect AI-generated phishing, synthetic voice impersonation, and social manipulation — while verifying the authenticity of official communications.
        </p>
      </div>

      {/* Stats */}
      <div className="mb-10 grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: "Detection Channels", value: "4", sub: "Phishing · Voice · Social · Image" },
          { label: "Allowlisted Entities", value: "18+", sub: "SEBI · NSE · BSE · Brokers · RTAs" },
          { label: "Evidence Sources", value: "12+", sub: "DOM · TLS · WHOIS · DNS · Vision" },
          { label: "Verification Speed", value: "<2s", sub: "Claim verification across 9 sources" },
        ].map((s, i) => (
          <div key={i} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{s.label}</div>
            <div className="mt-1 text-2xl font-extrabold text-sebiNavy">{s.value}</div>
            <div className="mt-0.5 text-[11px] text-slate-500">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Threat Coverage */}
      <div className="mb-10">
        <h2 className="mb-4 text-sm font-extrabold uppercase tracking-wider text-slate-600">Threat Coverage Matrix</h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Threat Vector</th>
                <th className="px-4 py-3">Securities Market Example</th>
                <th className="px-4 py-3">Impact</th>
                <th className="px-4 py-3">Detection</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[
                ["AI Phishing Emails", "Fake SEBI/Broker emails requesting KYC updates", "Credential theft", "LLM + Playwright + Vision"],
                ["Voice Cloning", "Fraudster impersonates Relationship Manager", "Fund diversion", "Signal analysis + provenance"],
                ["Deepfake Videos", "Fake CEO recommending stock purchase", "Market manipulation", "Pending — model integration"],
                ["Synthetic Social Posts", "AI-generated breaking news on listed companies", "Investor misinformation", "LLM + Web verification"],
                ["Fake Circulars", "Fraudulent regulatory announcements", "Investor panic", "Claim verification + allowlist"],
              ].map((row, i) => (
                <tr key={i} className="hover:bg-slate-50/50">
                  <td className="px-4 py-3 font-bold text-slate-800">{row[0]}</td>
                  <td className="px-4 py-3 text-slate-600">{row[1]}</td>
                  <td className="px-4 py-3 text-slate-600">{row[2]}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">{row[3]}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Link href="/scan" className="group rounded-xl border border-sebiTeal/20 bg-gradient-to-br from-sebiTeal/5 to-white p-6 shadow-sm transition hover:shadow-md">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-sebiTeal/10 text-sebiTeal">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          </div>
          <h3 className="text-sm font-bold text-sebiNavy group-hover:text-sebiTeal">Launch Scanner</h3>
          <p className="mt-1 text-xs text-slate-500">Submit emails, URLs, social posts, or audio for analysis.</p>
        </Link>
        <Link href="/registry" className="group rounded-xl border border-sky-100 bg-gradient-to-br from-sky-50 to-white p-6 shadow-sm transition hover:shadow-md">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-sky-100 text-sky-600">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          </div>
          <h3 className="text-sm font-bold text-slate-800 group-hover:text-sky-600">Trust Registry</h3>
          <p className="mt-1 text-xs text-slate-500">View the official domain allowlist and known market entities.</p>
        </Link>
        <Link href="/about" className="group rounded-xl border border-amber-100 bg-gradient-to-br from-amber-50 to-white p-6 shadow-sm transition hover:shadow-md">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <h3 className="text-sm font-bold text-slate-800 group-hover:text-amber-600">About TrustShield</h3>
          <p className="mt-1 text-xs text-slate-500">Learn about the architecture, methodology, and MSE problem statement.</p>
        </Link>
      </div>
    </div>
  );
}
