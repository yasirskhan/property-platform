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
type Filter = { bank_id: string; date_from?: string; date_to?: string };

export default function BankActivityPage() {
  const [bankId, setBankId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Filter | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const params: Filter = {
      bank_id: bankId,
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    };
    try {
      const query = new URLSearchParams(params);
      const data = await apiGet(
        `/api/reporting/bank-activity/preview?${query.toString()}`
      ) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Bank book report unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Bank Account Activity</h1>
        <p className="mt-1 text-sm text-slate-600">
          Posted GL book movements on the cash account linked to the selected bank account.
          This is not a bank statement, cleared balance, live feed or proof of settlement.
          Private bank numbers are never included. The report requires accrual presentation.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">
          Bank account ID
          <input required type="number" min={1} step={1} value={bankId}
            onChange={(event) => setBankId(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Posted date from
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Posted date to
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load posted bank book"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="accounting.bank_activity" parameters={applied} />
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
                    {row.map((value, col) =>
                      <td key={col} className="px-3 py-2">{String(value ?? "")}</td>)}
                  </tr>)}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
