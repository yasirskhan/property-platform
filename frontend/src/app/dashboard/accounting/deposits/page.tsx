// ============================================================
// Bank Deposits list page
// ------------------------------------------------------------
// Group un-deposited receipts into a batch for the bank.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listDeposits,
  getDeposit,
  type Deposit,
  type DepositDetail,
  type DepositListFilters,
} from "@/lib/deposits";
import { formatMoney } from "@/lib/money";

interface Me {
  id: number;
  role: string;
}

export default function DepositsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<Deposit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [bankAccount, setBankAccount] = useState<number | "">("");

  const [openDeposit, setOpenDeposit] = useState<DepositDetail | null>(null);
  const [openLoading, setOpenLoading] = useState(false);

  useEffect(() => {
    fetch("/auth/me", {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((u) => setMe(u))
      .catch(() => setMe(null));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const filters: DepositListFilters = {};
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      if (bankAccount) filters.bank_gl_account_id = bankAccount;
      const data = await listDeposits(filters);
      setRows(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load deposits.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function open(depositId: number) {
    setOpenLoading(true);
    setError(null);
    try {
      const detail = await getDeposit(depositId);
      setOpenDeposit(detail);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load deposit.");
    } finally {
      setOpenLoading(false);
    }
  }

  const totalAmount = rows.reduce((acc, d) => acc + parseFloat(d.total), 0);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-900">Bank Deposits</h1>
        {me && me.role !== "TENANT" && (
          <Link
            href="/dashboard/accounting/deposits/new"
            className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
          >
            + New Deposit
          </Link>
        )}
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Group receipts into a batch for the bank.
      </p>

      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-slate-600 mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">
            Bank GL Account ID
          </label>
          <input
            type="number"
            value={bankAccount}
            onChange={(e) =>
              setBankAccount(e.target.value ? Number(e.target.value) : "")
            }
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm w-32"
          />
        </div>
        <button
          type="button"
          onClick={load}
          className="px-3 py-1.5 rounded-md bg-slate-700 text-white text-sm font-medium hover:bg-slate-800"
        >
          Show
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-600 mb-3 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Deposit #</th>
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Bank Account</th>
              <th className="text-left px-4 py-2 font-medium">Description</th>
              <th className="text-right px-4 py-2 font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  No deposits yet.
                </td>
              </tr>
            )}
            {rows.map((d) => (
              <tr
                key={d.id}
                onClick={() => open(d.id)}
                className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
              >
                <td className="px-4 py-2 font-mono text-xs">
                  {d.deposit_number || `#${d.id}`}
                </td>
                <td className="px-4 py-2">{d.deposit_date}</td>
                <td className="px-4 py-2 text-slate-500">
                  {d.bank_gl_account_number
                    ? `${d.bank_gl_account_number} ${d.bank_gl_account_name}`
                    : `GL #${d.bank_gl_account_id}`}
                </td>
                <td className="px-4 py-2 text-slate-500">
                  {d.description || "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(d.total)}
                </td>
              </tr>
            ))}
          </tbody>
          {rows.length > 0 && (
            <tfoot className="bg-slate-50 text-slate-700">
              <tr className="border-t border-slate-200">
                <td className="px-4 py-2 text-xs" colSpan={4}>
                  {rows.length} deposits
                </td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(totalAmount.toFixed(2))}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Detail modal */}
      {(openDeposit || openLoading) && (
        <div
          className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center p-6 overflow-auto"
          onClick={() => setOpenDeposit(null)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full my-8 max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {openLoading && !openDeposit ? (
              <div className="p-8 text-center text-slate-500">Loading...</div>
            ) : openDeposit ? (
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">
                      {openDeposit.deposit_number || `#${openDeposit.id}`}
                    </h2>
                    <div className="text-sm text-slate-500">
                      {openDeposit.deposit_date}
                      {openDeposit.bank_gl_account_number && (
                        <>
                          {" · "}
                          {openDeposit.bank_gl_account_number}{" "}
                          {openDeposit.bank_gl_account_name}
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => setOpenDeposit(null)}
                    className="text-slate-400 hover:text-slate-700 text-xl leading-none"
                  >
                    ✕
                  </button>
                </div>

                {openDeposit.description && (
                  <div className="text-sm text-slate-600 mb-4">
                    {openDeposit.description}
                  </div>
                )}

                <div className="text-sm text-slate-600 mb-4">
                  Total:{" "}
                  <span className="font-mono">
                    {formatMoney(openDeposit.total)}
                  </span>
                </div>

                <div className="border border-slate-200 rounded-md overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">
                          Receipt
                        </th>
                        <th className="text-left px-3 py-2 font-medium">
                          Date
                        </th>
                        <th className="text-left px-3 py-2 font-medium">
                          Payer
                        </th>
                        <th className="text-right px-3 py-2 font-medium">
                          Amount
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {openDeposit.lines.map((ln) => (
                        <tr key={ln.id} className="border-t border-slate-100">
                          <td className="px-3 py-2">
                            {ln.receipt_type}
                            {ln.receipt_date && (
                              <span className="text-slate-500">
                                {" · "}
                                {ln.receipt_date}
                              </span>
                            )}
                            {ln.receipt_reference && (
                              <span className="text-slate-500">
                                {" · ref "}
                                {ln.receipt_reference}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-slate-500">
                            {ln.receipt_date || "—"}
                          </td>
                          <td className="px-3 py-2 text-slate-500">
                            {ln.receipt_payer || "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono">
                            {ln.receipt_amount
                              ? formatMoney(ln.receipt_amount)
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="text-xs text-slate-500 mt-4">
                  Bank deposits cannot be reversed. Correct via a journal entry.
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}