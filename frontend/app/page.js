"use client";
import Link from "next/link";

export default function Dashboard() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-16 md:py-24">
      <div className="mb-14">
        <h1 className="text-4xl font-black tracking-tight text-slate-900">
          Trust<span className="text-brand">Shield</span>
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-500">
          A multimodal trust layer for India's securities markets. Verify whether a communication is genuine or a threat — phishing, synthetic voice, social manipulation — before you act on it.
        </p>
      </div>

      <div className="mb-12 grid grid-cols-3 gap-3">
        {[
          { v: "Email", d: "Phishing & impersonation" },
          { v: "Voice", d: "Deepfake & vishing" },
          { v: "Social", d: "Manipulation & fraud" },
        ].map((c, i) => (
          <div key={i} className="rounded-xl border border-slate-200/60 bg-white p-4">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{c.v}</div>
            <div className="mt-1 text-[11px] font-medium text-slate-600">{c.d}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Link href="/scan" className="group rounded-2xl border border-slate-200/60 bg-white p-6 transition hover:shadow-md hover:border-slate-300">
          <h3 className="text-lg font-bold text-slate-900">Check a communication</h3>
          <p className="mt-1.5 text-sm text-slate-500">Paste an email, message, URL, or upload audio for instant verification.</p>
          <div className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 group-hover:translate-x-0.5 transition-transform">
            Start scan <span aria-hidden="true">→</span>
          </div>
        </Link>
        <Link href="/registry" className="group rounded-2xl border border-slate-200/60 bg-white p-6 transition hover:shadow-md hover:border-slate-300">
          <h3 className="text-lg font-bold text-slate-900">Trust Registry</h3>
          <p className="mt-1.5 text-sm text-slate-500">View the allowlisted domains, brokers, RTAs, and regulators TrustShield recognizes.</p>
          <div className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 group-hover:translate-x-0.5 transition-transform">
            Browse registry <span aria-hidden="true">→</span>
          </div>
        </Link>
      </div>
    </main>
  );
}
