// ============================================================
// Deposits list page
// ------------------------------------------------------------
// Route: /dashboard/accounting/deposits
//
// Shows every bank deposit in the current org. Clicking a row
// opens a centered modal with the deposit's receipts.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listDeposits,
  Deposit,
  DepositList,
} from "@/lib/deposits";
import { apiGet } from "@/lib/api";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function DepositsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<DepositList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [selected, setSelected] = useState<Deposit | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listDeposits({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setData(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo]);

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  const canWrite = me ? WRITE_ROLES.includes(me.role) : false;

  const totalAmount = data.items.reduce(
    (sum, d) => sum + Number(d.total || 0),
    0
  );

  return (
    <div>
      {/* Back link */}
      <div className="mb-4">
        <button
          type="button"
          onClick={() => {
            if (typeof window !== "undefined" && window.history.length > 1) {
              window.history.back();
            } else {
              window.location.href = "/dashboard";
            }
          }}
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back
        </button>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Bank Deposits</h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "deposit" : "deposits"}
            {" · "}
            Total:{" "}
            {totalAmount.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
            })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/accounting/receipts"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Receipts
          </Link>
          <Link
            href="/dashboard/accounting/bills"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Bills
          </Link>
          {canWrite && (
            <Link
              href="/dashboard/accounting/deposits/new"
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + New Deposit
            </Link>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Date from</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Date to</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-32">
                Deposit #
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Date
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-48">
                Bank Account
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Description
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-24">
                Receipts
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No deposits yet.
                </td>
              </tr>
            )}
            {data.items.map((d) => (
              <tr
                key={d.id}
                onClick={() => setSelected(d)}
                className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
              >
                <td className="px-4 py-2 text-slate-500 font-mono">
                  {d.deposit_number || `#${d.id}`}
                </td>
                <td className="px-4 py-2 text-slate-700">{d.deposit_date}</td>
                <td className="px-4 py-2 text-slate-700 text-xs">
                  {d.bank_gl_account_number
                    ? `${d.bank_gl_account_number} ${d.bank_gl_account_name}`
                    : "—"}
                </td>
                <td className="px-4 py-2 text-slate-600">
                  {d.description || "—"}
                </td>
                <td className="px-4 py-2 text-right text-slate-600 font-mono">
                  {d.line_count}
                </td>
                <td className="px-4 py-2 text-right font-mono font-semibold">
                  {Number(d.total).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Centered modal */}
      {selected && (
        <DepositDetailModal
          deposit={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Centered modal: deposit detail with receipts
// ------------------------------------------------------------
function DepositDetailModal({
  deposit,
  onClose,
}: {
  deposit: Deposit;
  onClose: () => void;
}) {
  const [lines, setLines] = useState<
    Array<{
      id: number;
      receipt_id: number;
      receipt_date: string | null;
      receipt_type: string | null;
      receipt_amount: string | null;
      receipt_reference: string | null;
      receipt_payer: string | null;
    }>
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const { getDeposit } = await import("@/lib/deposits");
        const detail = await getDeposit(deposit.id);
        if (!cancelled) setLines(detail.lines);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [deposit.id]);

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="w-full max-w-2xl max-h-[90vh] bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
            <div>
              <div className="text-xs text-slate-500">Deposit</div>
              <div className="font-semibold text-slate-900 text-lg">
                {deposit.deposit_number || `#${deposit.id}`}
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-700 text-2xl leading-none"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Date</div>
                <div className="text-slate-800">{deposit.deposit_date}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Total</div>
                <div className="text-slate-800 font-mono text-lg">
                  {Number(deposit.total).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Bank Account</div>
                <div className="text-slate-800">
                  {deposit.bank_gl_account_number}{" "}
                  {deposit.bank_gl_account_name}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Receipts</div>
                <div className="text-slate-800">{deposit.line_count}</div>
              </div>
            </div>

            {deposit.description && (
              <div>
                <div className="text-xs text-slate-500">Description</div>
                <div className="text-slate-800">{deposit.description}</div>
              </div>
            )}

            {deposit.notes && (
              <div>
                <div className="text-xs text-slate-500">Notes</div>
                <div className="text-slate-800 whitespace-pre-wrap">
                  {deposit.notes}
                </div>
              </div>
            )}

            <div className="pt-4 border-t border-slate-200">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                Receipts in this deposit
              </div>
              {loading ? (
                <div className="text-slate-500 text-xs">Loading…</div>
              ) : lines.length === 0 ? (
                <div className="text-slate-500 text-xs">No receipts.</div>
              ) : (
                <ul className="space-y-2">
                  {lines.map((ln) => (
                    <li
                      key={ln.id}
                      className="flex items-start justify-between text-xs border-b border-slate-100 pb-2"
                    >
                      <div>
                        <div className="text-slate-700">
                          Receipt #{ln.receipt_id}
                          {ln.receipt_date && ` · ${ln.receipt_date}`}
                        </div>
                        <div className="text-slate-500">
                          {ln.receipt_payer}
                          {ln.receipt_type && ` · ${ln.receipt_type}`}
                          {ln.receipt_reference &&
                            ` · ref ${ln.receipt_reference}`}
                        </div>
                      </div>
                      <div className="font-mono text-slate-800">
                        {ln.receipt_amount
                          ? Number(ln.receipt_amount).toLocaleString("en-US", {
                              style: "currency",
                              currency: "USD",
                            })
                          : "—"}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}