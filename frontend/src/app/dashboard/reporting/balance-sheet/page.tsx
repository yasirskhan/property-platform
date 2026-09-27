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

export default function BalanceSheetPage() {
  const [asOf, setAsOf] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<{ as_of: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    if (!asOf) { setBusy(false); setError("Choose a balance sheet date."); return; }
    try {
      const data = await apiGet(
        `/api/reporting/balance-sheet/preview?as_of=${encodeURIComponent(asOf)}`
      ) as Preview;
      setPreview(data); setApplied({ as_of: asOf });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Balance sheet unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Balance Sheet</h1>
        <p className="mt-1 text-sm text-slate-600">
          Posted accrual GL balances as of a selected date. Income less expense
          not closed to equity is shown separately. This unaudited statement
          excludes property appraisals, unrecorded liabilities and bank-reconciliation claims.
          The report refuses to render if the posted GL does not balance.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">
          Balance sheet as of
          <input required type="date" value={asOf}
            onChange={(event) => setAsOf(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Generate balance sheet"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="accounting.balance_sheet" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[760px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) =>
                  <th key={header} scope="col" className="px-3 py-2 text-left font-semibold">{header}</th>)}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, idx) =>
                  <tr key={idx} className="border-t">
                    {row.map((value, col) =>
                      <td key={col} className="px-3 py-2">{String(value)}</td>)}
                  </tr>)}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
