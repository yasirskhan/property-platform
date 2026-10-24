"use client";

import { useState } from "react";
import Link from "next/link";
import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = {
  title: string;
  headers: string[];
  rows: (string | number)[][];
  total: number;
};

export default function AgedPayablesPage() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null);
    try {
      const data = await apiGet("/api/reporting/aged-payables/preview") as Preview;
      setPreview(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Aged payables unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Aged Payables</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current open recorded bill amounts aged against their due dates.
          This is an accrual-only current-state view, not historical as-of
          accounts payable or verified cleared bank payments. Bills without
          recorded due dates appear in a separate bucket.
        </p>
      </header>
      <button disabled={busy} type="button" onClick={() => { void load(); }}
        className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
        {busy ? "Loading…" : "Load current aged payables"}
      </button>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="transaction.aged_payables" />
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
