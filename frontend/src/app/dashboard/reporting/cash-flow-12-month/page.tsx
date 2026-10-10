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

export default function CashFlowTwelveMonthPage() {
  const [endingMonth, setEndingMonth] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<{ ending_month: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setPreview(null);
    setApplied(null);
    try {
      const query = new URLSearchParams({ ending_month: endingMonth });
      const data = await apiGet(
        `/api/reporting/cash-flow-12-month/preview?${query.toString()}`
      ) as Preview;
      setPreview(data);
      setApplied({ ending_month: endingMonth });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Twelve-month cash flow unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Cash Flow — 12 Months</h1>
        <p className="mt-1 text-sm text-slate-600">
          Twelve complete calendar months of posted bank-mapped GL book cash.
          This is not a classified or audited cash-flow statement or a
          cleared bank balance. Transfers inflate gross amounts but cancel
          in net; unmapped or excluded accounts are omitted.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">
          Ending month
          <input required type="month" value={endingMonth}
            onChange={(event) => setEndingMonth(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button disabled={busy} type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load twelve-month report"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="accounting.cash_flow_12_month" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-full divide-y text-left text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{header}</th>
                ))}
              </tr></thead>
              <tbody className="divide-y">
                {preview.rows.map((row, index) => (
                  <tr key={index}>
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
