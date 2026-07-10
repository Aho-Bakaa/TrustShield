import "./globals.css";

export const metadata = {
  title: "TrustShield — Investor Trust & Verification Layer",
  description: "Multimodal detection of AI-generated phishing, synthetic voice, and social manipulation for securities-market communications.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-800 antialiased">
        <div className="flex min-h-screen flex-col">
          <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur">
            <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 md:px-6">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sebiNavy text-white">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/></svg>
                </div>
                <div>
                  <a href="/" className="text-sm font-extrabold tracking-tight text-sebiNavy">TrustShield</a>
                  <div className="text-[9px] font-bold uppercase tracking-widest text-slate-400">SEBI Investor Trust Protocol</div>
                </div>
              </div>
              <nav className="flex items-center gap-1">
                <a href="/" className="rounded-md px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100">Dashboard</a>
                <a href="/scan" className="rounded-md px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100">Scanner</a>
                <a href="/registry" className="rounded-md px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100">Registry</a>
                <a href="/about" className="rounded-md px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100">About</a>
              </nav>
            </div>
          </header>
          <main className="flex-1">{children}</main>
          <footer className="border-t border-slate-200 bg-white py-6 text-center">
            <div className="mx-auto max-w-7xl px-4 md:px-6">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Securities and Exchange Board of India · TrustShield Verification Protocol
              </div>
              <div className="mt-1 text-[9px] text-slate-300">
                PS1 — Multimodal AI Threat Detection for Securities Market Integrity
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
