// ============================================================
// Ledger Page
// ------------------------------------------------------------
// Route: /dashboard/accounting/gl-accounts/{id}/ledger
//
// Shows every posted entry for one GL account, with a running
// balance after each line. Filterable by date range and
// property.
//
// Balances follow the standard rule: balance = debits - credits.
// For ASSET and EXPENSE accounts this is the natural direction.
// For LIABILITY and INCOME it's the opposite, but we still show
// debit-minus-credit so the numbers add up across the trial balance.
// ============================================================

"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import {
  getAccountLedger,
  Ledger,
  formatMoney,
  formatBalance,
} from "@/lib/glTransactions";
import { apiGet } from "@/lib/api";

type Props = {
  params: Promise<{ id: string }>;
};

export default function LedgerPage({ params }: Props) {
  const { id } = use(params);
  const accountId = Number(id);

  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Properties for filter dropdown
  const [properties, setProperties] = useState<{ id: number; name: string }[]>([]);
  const [propertyId, setPropertyId] = useState<number | "">("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await getAccountLedger(accountId, {
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        property_id: propertyId === "" ? undefined : propertyId,
      });
      setLedger(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, dateFrom, dateTo, propertyId]);

  useEffect(() => {
    apiGet("/properties")
      .then((data: { id: number; name: string }[]) => setProperties(data))
      .catch(() => setProperties([]));
  }, []);

  if (error) {
    return (
      <div>
        <Link
          href="/dashboard/accounting/gl-accounts"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Chart of Accounts
        </Link>
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  if (loading && !ledger) {
    return <div className="text-slate-500">Loading…</div>;
  }

  if (!ledger) return null;

  return (
    <div>
      {/* Breadcrumb */}
      <Link
        href="/dashboard/accounting/gl-accounts"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Chart of Accounts
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-baseline gap-3">
          <span className="text-sm font-mono text-slate-500">
            {ledger.gl_number}
          </span>
          <h1 className="text-2xl font-bold text-slate-900">
            {ledger.name}
          </h1>
        </div>
        <p className="text-sm text-slate-500 mt-1">
          {ledger.account_type} · Ledger
        </p>
      </div>

      {/* Summary card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="p-4 bg-white border border-slate-200 rounded-lg">
          <div className="text-xs text-slate-500 uppercase tracking-wide">
            Opening balance
          </div>
          <div className="text-lg font-semibold text-slate-900 mt-1">
            {formatBalance(ledger.opening_balance)}
          </div>
        </div>
        <div className="p-4 bg-white border border-slate-200 rounded-lg">
          <div className="text-xs text-slate-500 uppercase tracking-wide">
            Entries shown
          </div>
          <div className="text-lg font-semibold text-slate-900 mt-1">
            {ledger.lines.length}
          </div>
        </div>
        <div className="p-4 bg-white border border-slate-200 rounded-lg">
          <div className="text-xs text-slate-500 uppercase tracking-wide">
            Closing balance
          </div>
          <div className="text-lg font-semibold text-slate-900 mt-1">
            {formatBalance(ledger.closing_balance)}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-3 py-1.5 border border-slate-300 rounded text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-3 py-1.5 border border-slate-300 rounded text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Property</label>
          <select
            value={propertyId}
            onChange={(e) =>
              setPropertyId(e.target.value === "" ? "" : Number(e.target.value))
            }
            className="px-3 py-1.5 border border-slate-300 rounded text-sm"
          >
            <option value="">All properties</option>
            {properties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        {(dateFrom || dateTo || propertyId !== "") && (
          <button
            onClick={() => {
              setDateFrom("");
              setDateTo("");
              setPropertyId("");
            }}
            className="text-xs text-slate-500 hover:text-slate-900 mt-4"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Ledger table */}
      {ledger.lines.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-slate-500">
          No entries in this account for the selected filters.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Date
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-24">
                  Type
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Ref
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Description
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-32">
                  Debit
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-32">
                  Credit
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-32">
                  Balance
                </th>
              </tr>
            </thead>
            <tbody>
              {ledger.lines.map((line) => (
                <tr
                  key={line.entry_id}
                  className="border-t border-slate-100 hover:bg-slate-50"
                >
                  <td className="px-3 py-2 text-slate-700">
                    {line.transaction_date}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      href={`/dashboard/accounting/journal-entries/${line.transaction_id}`}
                      className="text-blue-600 hover:underline text-xs"
                      title="View transaction"
                    >
                      {line.transaction_type}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-500 text-xs">
                    {line.reference_number || "—"}
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    {line.description || line.memo || "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-slate-700">
                    {formatMoney(line.debit)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-slate-700">
                    {formatMoney(line.credit)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono font-medium text-slate-900">
                    {formatBalance(line.running_balance)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}