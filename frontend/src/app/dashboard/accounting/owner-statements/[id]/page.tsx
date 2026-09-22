// ============================================================
// Owner Statement detail page
// ------------------------------------------------------------
// Frozen snapshot. Print / Save as PDF via window.print().
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { formatMoney, formatDate } from "@/lib/money";
import {
  getOwnerStatement,
  type OwnerStatementDetail,
} from "@/lib/ownerStatements";

export default function OwnerStatementDetailPage() {
  const params = useParams<{ id: string }>();
  const statementId = Number(params.id);

  const [stmt, setStmt] = useState<OwnerStatementDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!statementId) return;
    getOwnerStatement(statementId)
      .then(setStmt)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load statement.")
      )
      .finally(() => setLoading(false));
  }, [statementId]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6 text-slate-500">Loading...</div>
    );
  }

  if (error || !stmt) {
    return (
      <div className="max-w-4xl mx-auto p-6 text-red-600">
        {error || "Not found."}
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6 print:hidden">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            Owner Statement
          </h1>
          <div className="text-sm text-slate-500">
            {stmt.owner_name || stmt.owner_email || `Owner #${stmt.owner_id}`}
          </div>
        </div>
        <div className="flex gap-3 items-center">
          <span className="text-xs text-slate-500">
            Generated{" "}
            {stmt.generated_at ? formatDate(stmt.generated_at) : "—"}
          </span>
          <button
            type="button"
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
          >
            Print / Save PDF
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-6 mb-5">
        <div className="grid grid-cols-2 gap-3 mb-6 text-sm">
          <div>
            <div className="text-xs text-slate-500">Period</div>
            <div className="font-medium">
              {stmt.period_start} → {stmt.period_end}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Beginning cash</div>
            <div className="font-mono">
              {formatMoney(stmt.total_beginning_cash)}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Total income</div>
            <div className="font-mono">{formatMoney(stmt.total_income)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Total expense</div>
            <div className="font-mono">{formatMoney(stmt.total_expense)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Ending cash</div>
            <div className="font-mono">
              {formatMoney(stmt.total_ending_cash)}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Net</div>
            <div className="font-mono font-semibold">
              {formatMoney(stmt.total_net)}
            </div>
          </div>
        </div>

        {stmt.properties.map((p) => (
          <div key={p.property_id} className="mt-6 pt-6 border-t border-slate-200">
            <h3 className="text-base font-semibold text-slate-900 mb-3">
              {p.property_name}{" "}
              <span className="text-xs text-slate-500 font-normal">
                ({p.ownership_pct}%)
              </span>
            </h3>

            <div className="grid grid-cols-4 gap-3 mb-4 text-sm">
              <div>
                <div className="text-xs text-slate-500">Beginning</div>
                <div className="font-mono">
                  {formatMoney(p.beginning_cash)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Income</div>
                <div className="font-mono">{formatMoney(p.income)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Expense</div>
                <div className="font-mono">{formatMoney(p.expense)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Ending</div>
                <div className="font-mono">{formatMoney(p.ending_cash)}</div>
              </div>
            </div>

            <div className="border border-slate-200 rounded-md overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Date</th>
                    <th className="text-left px-3 py-2 font-medium">
                      Description
                    </th>
                    <th className="text-left px-3 py-2 font-medium">
                      Reference
                    </th>
                    <th className="text-right px-3 py-2 font-medium">Income</th>
                    <th className="text-right px-3 py-2 font-medium">
                      Expense
                    </th>
                    <th className="text-right px-3 py-2 font-medium">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {p.transactions.map((t, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-1.5">{formatDate(t.date)}</td>
                      <td className="px-3 py-1.5">{t.description || "—"}</td>
                      <td className="px-3 py-1.5 text-slate-500">
                        {t.reference || "—"}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">
                        {formatMoney(t.income)}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">
                        {formatMoney(t.expense)}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">
                        {formatMoney(t.running_balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}

        {stmt.notes && (
          <div className="mt-6 pt-6 border-t border-slate-200 text-sm text-slate-600">
            <div className="text-xs text-slate-500 mb-1">Notes</div>
            {stmt.notes}
          </div>
        )}
      </div>
    </div>
  );
}