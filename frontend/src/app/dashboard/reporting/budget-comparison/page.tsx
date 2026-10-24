"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet, apiPut } from "@/lib/api";

type BudgetLine = {
  id: number; property_id: number; gl_account_id: number;
  calendar_year: number; month: number; amount: string;
};
type Preview = { title: string; headers: string[]; rows: (string | number)[][]; total: number };
type Viewer = { role: string };

export default function BudgetComparisonPage() {
  const [role, setRole] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [accountId, setAccountId] = useState("");
  const [month, setMonth] = useState("1");
  const [amount, setAmount] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [lines, setLines] = useState<BudgetLine[]>([]);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet("/auth/me").then((me: Viewer) => setRole(me.role))
      .catch(() => setError("Unable to load your account permissions."));
  }, []);

  async function load(prop: string, period: string) {
    setBusy(true); setError(""); setMessage("");
    setPreview(null); setLines([]); setApplied({});
    const query = new URLSearchParams({ property_id: prop.trim(), calendar_year: period.trim() }).toString();
    try {
      const [result, saved] = await Promise.all([
        apiGet(`/api/reporting/budget-comparison/preview?${query}`) as Promise<Preview>,
        apiGet(`/api/reporting/property-budgets?${query}`) as Promise<BudgetLine[]>,
      ]);
      setPreview(result); setLines(saved);
      setApplied({ property_id: prop.trim(), calendar_year: period.trim() });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Budget comparison unavailable.");
    } finally { setBusy(false); }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPut("/api/reporting/property-budgets", {
        property_id: Number(propertyId), gl_account_id: Number(accountId),
        calendar_year: Number(year), month: Number(month), amount,
      });
      setAmount("");
      setMessage("Budget target saved. The general ledger was not modified.");
      await load(propertyId, year);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save budget target.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Property Budget Comparison</h1>
        <p className="mt-1 text-sm text-slate-600">
          Compare explicitly recorded monthly income and expense targets to
          posted property GL movements. This is an accrual-basis journal comparison,
          not a cash-basis statement. Reversals count alongside original postings.
          No budgets or GL actuals are inferred from property estimated rent.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(propertyId, year); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm font-medium text-slate-700">Property ID
          <input required min={1} type="number" step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-44 rounded-lg border border-slate-300 p-2" />
        </label>
        <label className="text-sm font-medium text-slate-700">Calendar year
          <input required min={2000} max={2100} type="number" step={1} value={year}
            onChange={(event) => setYear(event.target.value)}
            className="mt-1 block w-36 rounded-lg border border-slate-300 p-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load comparison"}
        </button>
      </form>
      {role === "ADMIN" && (
        <form onSubmit={(event) => { void save(event); }}
          className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="font-semibold text-slate-900">Set a monthly budget target</h2>
          <p className="text-sm text-slate-600">
            Use a valid income or expense GL account ID from your Chart of Accounts.
            Existing targets for the same property, account, year and month are replaced
            and audited. No accounting entry is posted.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm text-slate-700">Income/expense GL account ID
              <input required min={1} type="number" step={1} value={accountId}
                onChange={(event) => setAccountId(event.target.value)}
                className="mt-1 block w-48 rounded-lg border border-slate-300 p-2" />
            </label>
            <label className="text-sm text-slate-700">Month
              <select value={month} onChange={(event) => setMonth(event.target.value)}
                className="mt-1 block w-36 rounded-lg border border-slate-300 p-2">
                {Array.from({ length: 12 }, (_, i) => (
                  <option value={i + 1} key={i + 1}>{i + 1}</option>
                ))}
              </select>
            </label>
            <label className="text-sm text-slate-700">Budget amount
              <input required min={0} step={0.01} type="number" value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className="mt-1 block w-44 rounded-lg border border-slate-300 p-2" />
            </label>
            <button disabled={busy || !propertyId || !year} type="submit"
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
              Save budget target
            </button>
          </div>
        </form>
      )}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span><strong>{preview.total}</strong> configured monthly budget lines.</span>
            <ReportActions reportKey="property.budget_comparison" parameters={applied} />
          </div>
          <p className="text-xs text-slate-500">
            {lines.length} saved targets. Variance is favorable when positive.
            Blank results mean no target data was recorded; they are not zero-budget assumptions.
          </p>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-[1200px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th key={header} className="whitespace-nowrap px-3 py-2 text-left font-semibold" scope="col">{header}</th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, idx) => (
                  <tr key={idx} className="border-t border-slate-100">
                    {row.map((value, col) => <td key={col} className="whitespace-nowrap px-3 py-2">{String(value)}</td>)}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No monthly budget targets saved for this property/year.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
