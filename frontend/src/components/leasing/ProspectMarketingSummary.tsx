"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type SourceRow = {
  source: string; total: number; new: number; contacted: number;
  tour_scheduled: number; applied: number; closed: number;
};
type Summary = { items: SourceRow[]; total: number; meaning: string };

export default function ProspectMarketingSummary({ version }: { version: number }) {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const result = await apiGet("/api/leasing/prospects/source-summary") as Summary;
        if (active) { setData(result); setError(""); }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Source breakdown unavailable.");
      }
    })();
    return () => { active = false; };
  }, [version]);

  return <section className="rounded-xl border bg-white p-4">
    <h2 className="font-semibold text-slate-900">Marketing-source breakdown</h2>
    <p className="mt-1 text-xs text-slate-500">
      Staff-recorded active prospect stages only. These are not verified applications,
      advertising conversions, revenue or marketing return on investment.
    </p>
    {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
    {data && <>
      {data.items.length === 0
        ? <p className="mt-3 text-sm text-slate-500">No active prospects to summarize.</p>
        : <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="border-b text-slate-600">
              <th className="p-2">Source</th><th className="p-2">Total</th>
              <th className="p-2">New</th><th className="p-2">Contacted</th>
              <th className="p-2">Tour scheduled</th><th className="p-2">Marked applied</th>
              <th className="p-2">Closed</th>
            </tr></thead>
            <tbody>{data.items.map(row=><tr key={row.source} className="border-b">
              <th scope="row" className="p-2 font-medium">{row.source}</th>
              <td className="p-2">{row.total}</td><td className="p-2">{row.new}</td>
              <td className="p-2">{row.contacted}</td><td className="p-2">{row.tour_scheduled}</td>
              <td className="p-2">{row.applied}</td><td className="p-2">{row.closed}</td>
            </tr>)}</tbody>
          </table>
        </div>}
    </>}
  </section>;
}
