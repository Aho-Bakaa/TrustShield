"use client";
import Link from "next/link";

export default function Dashboard() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 md:px-6">
      <div className="mb-12">
        <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Securities and Exchange Board of India</div>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-sebiNavy">TrustShield</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-500">
          A multimodal trust and verification layer for India's securities-market communications. Detect AI-generated phishing, synthetic voice impersonation, and social manipulation — while verifying whether a purportedly official communication is genuine.
        </p>
      </div>

      <div className="mb-12 grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: "Detection Channels", value: "4", sub: "Email · URL · Social · Audio" },
          { label: "Trust Registry", value: "18+", sub: "SEBI · NSE · BSE · Brokers · RTAs" },
          { label: "Evidence Sources", value: "12+", sub: "DOM · TLS · WHOIS · DNS · Vision" },
          { label: "Pipeline", value: "LLM-first", sub: "Playwright · Vision · Search · Verdict" },
        ].map((s, i) => (
          <div key={i} className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{s.label}</div>
            <div className="mt-1 text-2xl font-extrabold text-sebiNavy">{s.value}</div>
            <div className="mt-0.5 text-[11px] text-slate-500">{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Link href="/scan" className="group rounded-xl border border-sebiTeal/20 bg-gradient-to-br from-sebiTeal/5 to-white p-6 transition hover:shadow-md">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-sebiTeal/10 text-sebiTeal">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          </div>
          <h3 className="text-sm font-bold text-sebiNavy group-hover:text-sebiTeal">Scan Communications</h3>
          <p className="mt-1 text-xs text-slate-500">Submit emails, URLs, social posts, or audio for threat analysis with Playwright-powered verification.</p>
        </Link>
        <Link href="/registry" className="group rounded-xl border border-sky-100 bg-gradient-to-br from-sky-50 to-white p-6 transition hover:shadow-md">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-sky-100 text-sky-600">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          </div>
          <h3 className="text-sm font-bold text-slate-800 group-hover:text-sky-600">Trust Registry</h3>
          <p className="mt-1 text-xs text-slate-500">View the official domain allowlist and known securities-market entities.</p>
        </Link>
      </div>
    </div>
  );
}
