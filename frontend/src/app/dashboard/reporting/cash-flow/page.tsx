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
type Parameters = { date_from: string; date_to: string };

export default function CashFlowPage() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Parameters | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true); setError(""); setPreview(null); setApplied(null);
    const params = { date_from: dateFrom, date_to: dateTo };
    try {
      const query = new URLSearchParams(params);
      const data = await apiGet(`/api/reporting/cash-flow/preview?${query.toString()}`) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cash flow report unavailable.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Cash Flow — Posted Bank Book</h1>
        <p className="mt-1 text-sm text-slate-600">
          Summarizes posted debit and credit movements on bank-mapped GL cash accounts
          configured for Cash Flow. It includes archived accounts with historical entries.
          Internal bank transfers inflate gross inflows and outflows but cancel in net.
          This is not a classified, audited cash flow statement or a cleared bank balance.
          Unmapped and excluded cash accounts are not included.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">Posted date from
          <input type="date" required value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">Posted date to
          <input type="date" required value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button type="submit" disabled={loading}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {loading ? "Loading…" : "Load posted cash movement"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="accounting.cash_flow" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-full divide-y text-left text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th scope="col" key={header} className="whitespace-nowrap px-3 py-2 font-medium">{header}</th>
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
