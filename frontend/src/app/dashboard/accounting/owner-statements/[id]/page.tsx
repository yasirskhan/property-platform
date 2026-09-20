// ============================================================
// Owner Statement detail / print page
// ------------------------------------------------------------
// Route: /dashboard/accounting/owner-statements/{id}
//
// Shows the FROZEN snapshot — the numbers don't change even if
// the underlying GL is edited later. That's the AppFolio model.
//
// Print-ready layout — use Ctrl+P to save as PDF.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getOwnerStatement,
  OwnerStatementDetail,
} from "@/lib/ownerStatements";

export default function OwnerStatementDetailPage() {
  const params = useParams();
  const id = Number(params?.id);

  const [stmt, setStmt] = useState<OwnerStatementDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    (async () => {
      setLoading(true);
      try {
        const s = await getOwnerStatement(id);
        setStmt(s);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  if (loading) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!stmt) return null;

  const money = (v: string | number) =>
    Number(v || 0).toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
    });

  return (
    <div className="max-w-4xl mx-auto">
      {/* Nav (hidden on print) */}
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Link
          href="/dashboard/accounting/owner-statements"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Owner Statements
        </Link>
        <button
          onClick={() => window.print()}
          className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
        >
          Print / Save as PDF
        </button>
      </div>

      {/* Statement */}
      <div className="bg-white border border-slate-200 rounded-xl p-8 print:border-0 print:p-0">
        {/* Header */}
        <div className="border-b border-slate-300 pb-4 mb-6">
          <div className="text-2xl font-bold text-slate-900">
            Owner Statement
          </div>
          <div className="text-sm text-slate-600 mt-1">
            {stmt.owner_name || stmt.owner_email || `Owner #${stmt.owner_id}`}
          </div>
          <div className="text-sm text-slate-600">
            Period: {stmt.period_start} → {stmt.period_end}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Generated:{" "}
            {stmt.generated_at
              ? new Date(stmt.generated_at).toLocaleString()
              : "—"}
          </div>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-50 rounded-lg p-3">
            <div className="text-xs text-slate-500">Beginning Cash</div>
            <div className="text-lg font-mono font-semibold text-slate-800 mt-1">
              {money(stmt.total_beginning_cash)}
            </div>
          </div>
          <div className="bg-green-50 rounded-lg p-3">
            <div className="text-xs text-green-700">Income</div>
            <div className="text-lg font-mono font-semibold text-green-800 mt-1">
              {money(stmt.total_income)}
            </div>
          </div>
          <div className="bg-red-50 rounded-lg p-3">
            <div className="text-xs text-red-700">Expense</div>
            <div className="text-lg font-mono font-semibold text-red-800 mt-1">
              {money(stmt.total_expense)}
            </div>
          </div>
          <div className="bg-slate-100 rounded-lg p-3">
            <div className="text-xs text-slate-700">Ending Cash</div>
            <div className="text-lg font-mono font-semibold text-slate-900 mt-1">
              {money(stmt.total_ending_cash)}
            </div>
          </div>
        </div>

        {/* Per-property blocks */}
        {stmt.properties.map((p) => (
          <div
            key={p.property_id}
            className="mb-8 print:break-inside-avoid"
          >
            <div className="flex items-baseline justify-between border-b border-slate-300 pb-1 mb-3">
              <div className="text-lg font-semibold text-slate-900">
                {p.property_name}
              </div>
              <div className="text-xs text-slate-500">
                {p.ownership_pct}% ownership
              </div>
            </div>

            {/* Property mini-summary */}
            <div className="grid grid-cols-4 gap-3 mb-3 text-sm">
              <div>
                <div className="text-xs text-slate-500">Beginning</div>
                <div className="font-mono">{money(p.beginning_cash)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Income</div>
                <div className="font-mono text-green-700">
                  {money(p.income)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Expense</div>
                <div className="font-mono text-red-700">
                  {money(p.expense)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Ending</div>
                <div className="font-mono font-semibold">
                  {money(p.ending_cash)}
                </div>
              </div>
            </div>

            {/* Transaction table */}
            <table className="w-full text-xs border border-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-2 py-1 font-medium text-slate-700 w-24">
                    Date
                  </th>
                  <th className="text-left px-2 py-1 font-medium text-slate-700">
                    Description
                  </th>
                  <th className="text-left px-2 py-1 font-medium text-slate-700 w-24">
                    Reference
                  </th>
                  <th className="text-right px-2 py-1 font-medium text-slate-700 w-24">
                    Income
                  </th>
                  <th className="text-right px-2 py-1 font-medium text-slate-700 w-24">
                    Expense
                  </th>
                  <th className="text-right px-2 py-1 font-medium text-slate-700 w-28">
                    Balance
                  </th>
                </tr>
              </thead>
              <tbody>
                {p.transactions.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-2 py-3 text-center text-slate-400"
                    >
                      No transactions.
                    </td>
                  </tr>
                )}
                {p.transactions.map((t, i) => (
                  <tr
                    key={i}
                    className="border-t border-slate-100"
                  >
                    <td className="px-2 py-1 text-slate-600">{t.date}</td>
                    <td className="px-2 py-1 text-slate-800">
                      {t.description || "—"}
                    </td>
                    <td className="px-2 py-1 text-slate-500">
                      {t.reference || "—"}
                    </td>
                    <td className="px-2 py-1 text-right font-mono text-green-700">
                      {Number(t.income) > 0 ? money(t.income) : ""}
                    </td>
                    <td className="px-2 py-1 text-right font-mono text-red-700">
                      {Number(t.expense) > 0 ? money(t.expense) : ""}
                    </td>
                    <td className="px-2 py-1 text-right font-mono text-slate-700">
                      {t.running_balance ? money(t.running_balance) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

        {stmt.properties.length === 0 && (
          <div className="text-center text-slate-500 py-8">
            This owner has no properties with activity in the period.
          </div>
        )}

        {/* Notes */}
        {stmt.notes && (
          <div className="mt-6 pt-4 border-t border-slate-200">
            <div className="text-xs font-semibold text-slate-500 uppercase mb-1">
              Notes
            </div>
            <div className="text-sm text-slate-700 whitespace-pre-wrap">
              {stmt.notes}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 pt-4 border-t border-slate-200 text-xs text-slate-400 text-center">
          Statement #{stmt.id} · Generated by the property management platform
        </div>
      </div>
    </div>
  );
}