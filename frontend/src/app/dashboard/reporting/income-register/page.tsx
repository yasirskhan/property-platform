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
type Filters = { date_from: string; date_to: string; account_id?: string };

export default function IncomeRegisterPage() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [accountId, setAccountId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Filters | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const params: Filters = {
      date_from: dateFrom, date_to: dateTo,
      ...(accountId.trim() ? { account_id: accountId.trim() } : {}),
    };
    try {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) query.set(key, String(value));
      const data = await apiGet(
        `/api/reporting/income-register/preview?${query.toString()}`
      ) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Income register unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Income Register</h1>
        <p className="mt-1 text-sm text-slate-600">
          Individual dated posted income GL entries, with recorded transaction
          references and signed credit-minus-debit amounts. Debit returns and reversals
          remain visible. Not a bank-cleared receipts record or cash-basis report.
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
        <label className="text-sm font-medium">Income GL account ID (optional)
          <input type="number" min={1} step={1} value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button disabled={busy} type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load income register"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="transaction.income_register" parameters={applied} />
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
                    {row.map((cell, j) => (
                      <td key={j} className="whitespace-nowrap px-3 py-2">{String(cell ?? "")}</td>
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
