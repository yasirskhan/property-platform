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
type Filter = { as_of?: string; include_zero?: boolean };

export default function AccountTotalsPage() {
  const [asOf, setAsOf] = useState("");
  const [includeZero, setIncludeZero] = useState(false);
  const [applied, setApplied] = useState<Filter | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const filters: Filter = {
      ...(asOf ? { as_of: asOf } : {}),
      ...(includeZero ? { include_zero: true } : {}),
    };
    try {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        query.set(key, String(value));
      }
      const result = await apiGet(`/api/reporting/account-totals/preview?${query.toString()}`) as Preview;
      setPreview(result); setApplied(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Account totals unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Account Totals</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorded posted general-ledger debits and credits, including reversal entries.
          Signed net is debit minus credit for every account type.
          This is an accrual-basis posting report, not a bank or cash-flow statement.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">
          Through date (optional)
          <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={includeZero}
            onChange={(event) => setIncludeZero(event.target.checked)} />
          Include zero-activity accounts
        </label>
        <button disabled={busy} type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load account totals"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.total} GL account{preview.total === 1 ? "" : "s"}.</span>
            <ReportActions reportKey="accounting.account_totals" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[850px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) =>
                  <th key={header} scope="col" className="px-3 py-2 text-left font-semibold">{header}</th>)}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, idx) =>
                  <tr key={idx} className="border-t">
                    {row.map((value, col) => <td key={col} className="px-3 py-2">{String(value)}</td>)}
                  </tr>)}
                {preview.total === 0 &&
                  <tr><td colSpan={preview.headers.length} className="p-5 text-center text-slate-500">
                    No posted GL activity matches these filters.
                  </td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
