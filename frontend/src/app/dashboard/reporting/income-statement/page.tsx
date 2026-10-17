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
type Filters = { date_from: string; date_to: string; include_zero?: boolean };

export default function IncomeStatementPage() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeZero, setIncludeZero] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Filters | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const filters: Filters = {
      date_from: dateFrom, date_to: dateTo,
      ...(includeZero ? { include_zero: true } : {}),
    };
    try {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) query.set(key, String(value));
      const data = await apiGet(
        `/api/reporting/income-statement/preview?${query.toString()}`
      ) as Preview;
      setPreview(data); setApplied(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Income statement unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Income Statement</h1>
        <p className="mt-1 text-sm text-slate-600">
          Unaudited, posted accrual income less expenses from recorded GL accounts.
          Includes posted reversals, credits and negative amounts.
          This is not cash-basis profit or an audited financial statement.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">Posted date from
          <input required type="date" value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">Posted date to
          <input required type="date" value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={includeZero}
            onChange={(event) => setIncludeZero(event.target.checked)} />
          Include all income and expense accounts
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load income statement"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="accounting.income_statement" parameters={applied} />
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
                  <tr key={i} className={String(row[0]).startsWith("TOTAL") || String(row[0]).startsWith("NET ") ? "bg-slate-50 font-semibold" : ""}>
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
