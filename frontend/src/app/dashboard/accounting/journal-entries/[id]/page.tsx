// ============================================================
// Transaction Viewer
// ------------------------------------------------------------
// Route: /dashboard/accounting/journal-entries/{id}
//
// Shows ONE transaction in full: the header (date, type, memo,
// source) and every line (debit and credit sides).
//
// This is the "whole picture" view an accountant needs — both
// sides of the entry, not just one account's view of it.
//
// Reachable from:
//   * The ledger page — clicking a transaction_type link
//   * The transactions list (once built)
//
// Money formatting comes from lib/money.ts so the org's currency
// setting is respected (Section 59). A small local formatBalance()
// wraps formatMoney() and preserves the "show $0.00 for zero"
// behavior that a totals row needs.
// ============================================================

"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { getTransaction, GLTransactionDetail } from "@/lib/glTransactions";
import { formatMoney, formatDate } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

// Totals column: show "$0.00" for null/zero, not an em-dash.
function formatBalance(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return formatMoney(0);
  }
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return formatMoney(0);
  return formatMoney(n);
}

type Props = {
  params: Promise<{ id: string }>;
};

export default function TransactionViewerPage({ params }: Props) {
  const { prefs } = useDisplay();
  const { id } = use(params);
  const txnId = Number(id);

  const [txn, setTxn] = useState<GLTransactionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getTransaction(txnId)
      .then(setTxn)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Load failed")
      )
      .finally(() => setLoading(false));
  }, [txnId]);

  if (loading) return <div className="text-slate-500">Loading…</div>;

  if (error) {
    return (
      <div>
        <Link
          href="/dashboard/accounting/gl-accounts"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  if (!txn) return null;

  const totalDebit = txn.entries.reduce(
    (sum, e) => sum + Number(e.debit || 0),
    0
  );
  const totalCredit = txn.entries.reduce(
    (sum, e) => sum + Number(e.credit || 0),
    0
  );

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
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Transaction #{txn.id}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {txn.transaction_type}
            {txn.reference_number ? ` · ${txn.reference_number}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {txn.is_reversed && (
            <span className="inline-flex items-center gap-1 text-xs px-2 py-1 bg-red-50 text-red-700 rounded">
              <RotateCcw className="w-3 h-3" />
              Reversed
            </span>
          )}
          {txn.reversal_of_id && (
            <Link
              href={`/dashboard/accounting/journal-entries/${txn.reversal_of_id}`}
              className="inline-flex items-center gap-1 text-xs px-2 py-1 bg-amber-50 text-amber-700 rounded hover:bg-amber-100"
            >
              <RotateCcw className="w-3 h-3" />
              Reversal of #{txn.reversal_of_id}
            </Link>
          )}
        </div>
      </div>

      {/* Meta card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="p-4 bg-white border border-slate-200 rounded-lg">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Date</dt>
              <dd className="text-slate-900 font-medium">
                {formatDate(txn.transaction_date)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Posted</dt>
              <dd className="text-slate-700">
                {txn.posted_at?.slice(0, 19).replace("T", " ")}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Reference</dt>
              <dd className="text-slate-700">
                {txn.reference_number || "—"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="p-4 bg-white border border-slate-200 rounded-lg">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Source</dt>
              <dd className="text-slate-700">
                {txn.source_type
                  ? `${txn.source_type}${
                      txn.source_id ? ` #${txn.source_id}` : ""
                    }`
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Total debits</dt>
              <dd className="text-slate-900 font-mono font-medium">
                {formatBalance(totalDebit)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Total credits</dt>
              <dd className="text-slate-900 font-mono font-medium">
                {formatBalance(totalCredit)}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Memo */}
      {txn.memo && (
        <div className="mb-6 p-4 bg-slate-50 border border-slate-200 rounded-lg">
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">
            Memo
          </div>
          <div className="text-sm text-slate-800 whitespace-pre-wrap">
            {txn.memo}
          </div>
        </div>
      )}

      {/* Lines */}
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
        Lines
      </h2>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-24">
                GL #
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Account
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Description
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Debit
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Credit
              </th>
            </tr>
          </thead>
          <tbody>
            {txn.entries.map((e) => (
              <tr key={e.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-mono text-slate-500">
                  {e.gl_account_number || "—"}
                </td>
                <td className="px-4 py-2 text-slate-800">
                  {e.gl_account_id ? (
                    <Link
                      href={`/dashboard/accounting/gl-accounts/${e.gl_account_id}/ledger`}
                      className="text-blue-600 hover:underline"
                    >
                      {e.gl_account_name || `Account #${e.gl_account_id}`}
                    </Link>
                  ) : (
                    e.gl_account_name || "—"
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600">
                  {e.description || "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono text-slate-700">
                  {formatMoney(e.debit)}
                </td>
                <td className="px-4 py-2 text-right font-mono text-slate-700">
                  {formatMoney(e.credit)}
                </td>
              </tr>
            ))}
            {/* Totals row */}
            <tr className="border-t-2 border-slate-300 bg-slate-50">
              <td colSpan={3} className="px-4 py-2 text-right text-slate-700 font-medium">
                Totals
              </td>
              <td className="px-4 py-2 text-right font-mono font-semibold text-slate-900">
                {formatBalance(totalDebit)}
              </td>
              <td className="px-4 py-2 text-right font-mono font-semibold text-slate-900">
                {formatBalance(totalCredit)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}