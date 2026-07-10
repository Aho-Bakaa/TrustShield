"use client";
import { useEffect, useState } from "react";

const REGISTRY = {
  official_domains: [
    { domain: "sebi.gov.in", entity: "Securities and Exchange Board of India (SEBI)", type: "Regulator" },
    { domain: "scores.sebi.gov.in", entity: "SEBI SCORES", type: "Regulator Platform" },
    { domain: "nseindia.com", entity: "National Stock Exchange (NSE)", type: "Exchange" },
    { domain: "bseindia.com", entity: "BSE Ltd", type: "Exchange" },
    { domain: "cdslindia.com", entity: "CDSL", type: "Depository" },
    { domain: "nsdl.co.in", entity: "NSDL", type: "Depository" },
    { domain: "rbi.org.in", entity: "Reserve Bank of India (RBI)", type: "Regulator" },
    { domain: "amfiindia.com", entity: "AMFI", type: "Industry Body" },
    { domain: "zerodha.com", entity: "Zerodha", type: "Broker" },
    { domain: "groww.in", entity: "Groww", type: "Broker" },
    { domain: "icicidirect.com", entity: "ICICI Direct", type: "Broker" },
    { domain: "kite.zerodha.com", entity: "Zerodha Kite", type: "Broker Platform" },
    { domain: "angelone.in", entity: "Angel One", type: "Broker" },
    { domain: "smartodr.in", entity: "SMART ODR Portal", type: "Official Platform" },
    { domain: "camsonline.com", entity: "CAMS", type: "RTA" },
    { domain: "digital.camsonline.com", entity: "CAMS Digital", type: "RTA" },
    { domain: "kfintech.com", entity: "KFintech", type: "RTA" },
    { domain: "mfs.kfintech.com", entity: "KFintech MFS", type: "RTA" },
  ],
  entities: [
    "SEBI", "RBI", "NSE", "BSE", "CDSL", "NSDL", "AMFI",
    "Zerodha", "Groww", "Angel One", "ICICI Direct",
    "CAMS", "KFintech", "Reliance Industries", "Adani Group",
    "Tata Group", "SMART ODR",
  ],
};

export default function Registry() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-6">
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold tracking-tight text-sebiNavy">Trust Registry</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-500">
          Official domain allowlist and known securities-market entities. Communications linking to these domains are verified as genuine official sources.
        </p>
      </div>

      <div className="mb-10">
        <h2 className="mb-4 text-sm font-extrabold uppercase tracking-wider text-slate-600">Allowlisted Domains</h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Domain</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {REGISTRY.official_domains.map((d, i) => (
                <tr key={i} className="hover:bg-slate-50/50">
                  <td className="px-4 py-3 font-mono text-xs font-bold text-sebiNavy">{d.domain}</td>
                  <td className="px-4 py-3 text-slate-600">{d.entity}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700">{d.type}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1 text-emerald-600">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Verified
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="mb-4 text-sm font-extrabold uppercase tracking-wider text-slate-600">Known Market Entities</h2>
        <div className="flex flex-wrap gap-2">
          {REGISTRY.entities.map((e, i) => (
            <span key={i} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm">{e}</span>
          ))}
        </div>
        <p className="mt-3 text-[10px] text-slate-400">These entities are used for impersonation detection. Messages claiming to be from these entities are checked against official domains.</p>
      </div>
    </div>
  );
}
