"use client";

import { useState } from "react";
import Link from "next/link";
import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = { title: string; headers: string[]; rows: (string | number)[][]; total: number };

export default function AgedReceivablesPage() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [propertyId, setPropertyId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState<Record<string, string>>({});

  async function load() {
    setBusy(true); setError(""); setPreview(null);
    const params = new URLSearchParams();
    if (propertyId.trim()) params.set("property_id", propertyId.trim());
    try {
      const data = await apiGet(`/api/reporting/aged-receivables/preview?${params}`) as Preview;
      setPreview(data);
      setApplied(Object.fromEntries(params.entries()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Aged receivables unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Aged Receivables</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current recorded unpaid rent invoices aged by their due date.
          This is not an historical, GL-posted or audited receivables statement.
          Standalone charges are intentionally excluded to prevent possible late-fee double counting;
          use the separate Unpaid Charges report to inspect them.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-slate-700">
          Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            placeholder="All accessible properties"
            className="ml-2 rounded border border-slate-300 px-3 py-2" />
        </label>
        <button disabled={busy} type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load current aged receivables"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="transaction.aged_receivables" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-full divide-y text-left text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{header}</th>
                ))}
              </tr></thead>
              <tbody className="divide-y">
                {preview.rows.map((row, i) => (
                  <tr key={i} className={row[0] === "BUCKET" || row[0] === "TOTAL" ? "bg-slate-50 font-semibold" : ""}>
                    {row.map((value, j) => (
                      <td key={j} className="whitespace-nowrap px-3 py-2">{String(value ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
