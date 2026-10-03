// ============================================================
// Bills list page
// ------------------------------------------------------------
// List all bills, filter, view detail modal, pay, reverse.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/money";
import Flag from "@/components/features/Flag";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { useDisplay } from "@/contexts/DisplayContext";
import {
  listBills,
  getBill,
  payBill,
  reverseBill,
  deleteBill,
  BILL_STATUS_LABELS,
  BILL_STATUS_COLORS,
  type Bill,
  type BillDetail,
  type BillListFilters,
} from "@/lib/bills";

interface Me {
  id: number;
  role: string;
}

export default function BillsPage() {
  const { prefs } = useDisplay();
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [status, setStatus] = useState<string>("");
  const [payeeSearch, setPayeeSearch] = useState("");

  const [openBill, setOpenBill] = useState<BillDetail | null>(null);
  const [openLoading, setOpenLoading] = useState(false);

  const [payOpen, setPayOpen] = useState(false);
  const [payAmount, setPayAmount] = useState("");
  const [payDate, setPayDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [payCash, setPayCash] = useState<number | "">("");
  const [payReference, setPayReference] = useState("");
  const [payRemarks, setPayRemarks] = useState("");
  const [cashAccounts, setCashAccounts] = useState<
    { id: number; gl_number: string; name: string }[]
  >([]);
  const [paySaving, setPaySaving] = useState(false);
  const [confirmReverseOpen, setConfirmReverseOpen] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    apiGet("/auth/me").then((u) => setMe(u as Me)).catch(() => setMe(null));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const filters: BillListFilters = {};
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      if (status) filters.status = status as BillListFilters["status"];
      if (payeeSearch) filters.payee_name = payeeSearch;
      const data = await listBills(filters);
      setRows(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load bills.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function open(billId: number) {
    setOpenLoading(true);
    setError(null);
    try {
      const detail = await getBill(billId);
      setOpenBill(detail);
      setPayCash(detail.cash_gl_account_id ?? "");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load bill.");
    } finally {
      setOpenLoading(false);
    }
  }

  async function loadCashAccounts() {
    try {
      const gls = await apiGet("/api/accounting/gl-accounts");
      const groups = (gls as {
        groups: { account_type: string; accounts: { id: number; gl_number: string; name: string }[] }[];
      }).groups;
      const cash = groups
        .filter((g) => (g.account_type || "").toUpperCase() === "ASSET")
        .flatMap((g) => g.accounts)
        .filter((a) => a.gl_number.startsWith("11"));
      setCashAccounts(cash);
    } catch {
      setCashAccounts([]);
    }
  }

  async function submitPay() {
    if (!openBill) return;
    const amt = parseFloat(payAmount);
    if (!amt || amt <= 0 || !payCash) {
      setError("Enter a valid amount and cash account.");
      return;
    }
    setPaySaving(true);
    setError(null);
    try {
      const updated = await payBill(openBill.id, {
        payment_date: payDate,
        cash_gl_account_id: payCash,
        amount: amt,
        reference_number: payReference || null,
        remarks: payRemarks || null,
      });
      setOpenBill(updated);
      setPayOpen(false);
      setPayAmount("");
      setPayReference("");
      setPayRemarks("");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not pay bill.");
    } finally {
      setPaySaving(false);
    }
  }

  async function submitReverse() {
    if (!openBill) return;
    setError(null);
    try {
      const updated = await reverseBill(openBill.id, {
        reversal_date: new Date().toISOString().slice(0, 10),
      });
      setOpenBill(updated);
      setConfirmReverseOpen(false);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not reverse bill.");
    }
  }

  async function submitDelete() {
    if (!openBill) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteBill(openBill.id, new Date().toISOString().slice(0, 10));
      setConfirmDeleteOpen(false);
      setOpenBill(null);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not delete bill.");
    } finally {
      setDeleting(false);
    }
  }

  const totalUnpaid = useMemo(
    () =>
      rows
        .filter((b) => b.status !== "PAID" && b.status !== "VOID")
        .reduce(
          (acc, b) => acc + (parseFloat(b.amount) - parseFloat(b.amount_paid)),
          0
        ),
    [rows]
  );

  return (
    <div className="p-6" data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()} data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-900">Bills</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Flag name="release.accounting.bills.recurring"><Link href="/dashboard/accounting/bills/recurring" className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50">Recurring Bills</Link></Flag>
          <Flag name="release.accounting.write_checks"><Link href="/dashboard/accounting/checks/write" className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50">Write Checks</Link></Flag>\n          <Flag name="release.accounting.write_checks"><Link href="/dashboard/accounting/checks" className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50">Checks</Link></Flag>
          <Flag name="release.accounting.vendor_credits"><Link href="/dashboard/accounting/bills/credits/new" className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50">Enter Credit</Link></Flag>
          <Flag name="release.accounting.bills.manual_post"><Link href="/dashboard/accounting/bills/recurring" className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50">Manually Post Bills</Link></Flag>
          <Flag name="release.accounting.owner_draw"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Owner Draw</button></Flag>
          <Flag name="release.accounting.tenant_payable"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Tenant Payable</button></Flag>
          <Flag name="release.maintenance.work_order_to_bill"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Work Order to Bill</button></Flag>
          {me && me.role !== "TENANT" && (
            <Link href="/dashboard/accounting/bills/new" className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">+ New Bill</Link>
          )}
        </div>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Payables. Enter, pay, and reverse vendor bills.
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
          <label className="block text-xs text-slate-600 mb-1">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white"
          >
            <option value="">All</option>
            <option value="UNPAID">Unpaid</option>
            <option value="PARTIAL">Partial</option>
            <option value="PAID">Paid</option>
            <option value="VOID">Void</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">Payee</label>
          <input
            type="text"
            value={payeeSearch}
            onChange={(e) => setPayeeSearch(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
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
              <th className="text-left px-4 py-2 font-medium">Bill #</th>
              <th className="text-left px-4 py-2 font-medium">Payee</th>
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Due</th>
              <th className="text-right px-4 py-2 font-medium">Amount</th>
              <th className="text-right px-4 py-2 font-medium">Balance</th>
              <th className="text-left px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  No bills yet.
                </td>
              </tr>
            )}
            {rows.map((b) => {
              const balance = parseFloat(b.amount) - parseFloat(b.amount_paid);
              return (
                <tr
                  key={b.id}
                  onClick={() => open(b.id)}
                  className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer ${
                    b.is_reversed ? "line-through opacity-60" : ""
                  }`}
                >
                  <td className="px-4 py-2 font-mono text-xs">
                    {b.bill_number || `#${b.id}`}
                  </td>
                  <td className="px-4 py-2">{b.payee_name}</td>
                  <td className="px-4 py-2">{formatDate(b.bill_date)}</td>
                  <td className="px-4 py-2">{b.due_date ? formatDate(b.due_date) : "—"}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {formatMoney(b.amount)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {b.status === "VOID" ? "—" : formatMoney(balance.toFixed(2))}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        BILL_STATUS_COLORS[b.status] || "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {BILL_STATUS_LABELS[b.status] || b.status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          {rows.length > 0 && (
            <tfoot className="bg-slate-50 text-slate-700">
              <tr className="border-t border-slate-200">
                <td className="px-4 py-2 text-xs" colSpan={5}>
                  {rows.length} bills · total unpaid
                </td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(totalUnpaid.toFixed(2))}
                </td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Detail modal */}
      {(openBill || openLoading) && (
        <div
          className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center p-6 overflow-auto"
          onClick={() => {
            setOpenBill(null);
            setPayOpen(false);
          }}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full my-8 max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {openLoading && !openBill ? (
              <div className="p-8 text-center text-slate-500">Loading...</div>
            ) : openBill ? (
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">
                      {openBill.bill_number || `#${openBill.id}`}
                    </h2>
                    <div className="text-sm text-slate-500">
                      {openBill.payee_name} · {formatDate(openBill.bill_date)}
                      {openBill.due_date && ` · due ${formatDate(openBill.due_date)}`}
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setOpenBill(null);
                      setPayOpen(false);
                    }}
                    className="text-slate-400 hover:text-slate-700 text-xl leading-none"
                  >
                    ✕
                  </button>
                </div>

                {openBill.is_reversed && (
                  <div className="text-sm text-red-600 mb-3 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                    This bill has been reversed.
                  </div>
                )}

                <div className="grid grid-cols-3 gap-3 mb-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-500">Amount</div>
                    <div className="font-mono">
                      {formatMoney(openBill.amount)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Paid</div>
                    <div className="font-mono">
                      {formatMoney(openBill.amount_paid)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Outstanding</div>
                    <div className="font-mono">
                      {formatMoney(
                        (
                          parseFloat(openBill.amount) -
                          parseFloat(openBill.amount_paid)
                        ).toFixed(2)
                      )}
                    </div>
                  </div>
                </div>

                {openBill.remarks && (
                  <div className="text-sm text-slate-600 mb-4">
                    <span className="text-xs text-slate-500">Remarks: </span>
                    {openBill.remarks}
                  </div>
                )}

                <div className="border border-slate-200 rounded-md overflow-hidden mb-4">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">
                          Account
                        </th>
                        <th className="text-left px-3 py-2 font-medium">
                          Description
                        </th>
                        <th className="text-right px-3 py-2 font-medium">
                          Amount
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {openBill.lines.map((ln) => (
                        <tr key={ln.id} className="border-t border-slate-100">
                          <td className="px-3 py-2">
                            {ln.gl_account_number} {ln.gl_account_name}
                          </td>
                          <td className="px-3 py-2">{ln.description || "—"}</td>
                          <td className="px-3 py-2 text-right font-mono">
                            {formatMoney(ln.amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {openBill.gl_transaction_id && (
                  <div className="text-xs text-slate-500 mb-4">
                    <Link
                      href={`/dashboard/accounting/journal-entries/${openBill.gl_transaction_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      View GL transaction
                    </Link>
                  </div>
                )}

                {/* Inline pay form */}
                {payOpen && !openBill.is_reversed && openBill.status !== "PAID" && (
                  <div className="bg-slate-50 border border-slate-200 rounded-md p-4 mb-4">
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className="block text-xs text-slate-600 mb-1">
                          Payment date
                        </label>
                        <input
                          type="date"
                          value={payDate}
                          onChange={(e) => setPayDate(e.target.value)}
                          className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-600 mb-1">
                          Amount
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={payAmount}
                          onChange={(e) => setPayAmount(e.target.value)}
                          className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-600 mb-1">
                          Cash account
                        </label>
                        <select
                          value={payCash}
                          onChange={(e) =>
                            setPayCash(
                              e.target.value ? Number(e.target.value) : ""
                            )
                          }
                          className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white"
                        >
                          <option value="">Select...</option>
                          {cashAccounts.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.gl_number} {a.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-600 mb-1">
                          Reference
                        </label>
                        <input
                          type="text"
                          value={payReference}
                          onChange={(e) => setPayReference(e.target.value)}
                          className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm"
                        />
                      </div>
                    </div>
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setPayOpen(false)}
                        className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-white"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={submitPay}
                        disabled={paySaving}
                        className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                      >
                        {paySaving ? "Paying..." : "Pay"}
                      </button>
                    </div>
                  </div>
                )}

                <span hidden aria-hidden="true" data-compat-slot="bills.reverse-after-partial-payment" />
                <div className="flex items-center justify-between">
                  <div className="flex gap-2">
                    {!openBill.is_reversed &&
                      openBill.status !== "PAID" &&
                      openBill.status !== "VOID" && (
                        <button
                          onClick={() => {
                            if (!payOpen) {
                              loadCashAccounts();
                              setPayCash(openBill.cash_gl_account_id ?? "");
                            }
                            setPayAmount(
                              (
                                parseFloat(openBill.amount) -
                                parseFloat(openBill.amount_paid)
                              ).toFixed(2)
                            );
                            setPayOpen((v) => !v);
                          }}
                          className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
                        >
                          {payOpen ? "Cancel pay" : "Pay bill"}
                        </button>
                      )}
                    {!openBill.is_reversed && openBill.status !== "PAID" && (
                      <button
                        onClick={() => setConfirmReverseOpen(true)}
                        className="px-3 py-1.5 rounded-md border border-red-300 text-red-700 text-sm font-medium hover:bg-red-50"
                      >
                        Reverse
                      </button>
                    )}
                    {!openBill.is_reversed &&
                      openBill.status === "UNPAID" &&
                      parseFloat(openBill.amount_paid) === 0 && (
                        <button
                          onClick={() => setConfirmDeleteOpen(true)}
                          className="px-3 py-1.5 rounded-md border border-red-300 text-red-700 text-sm font-medium hover:bg-red-50"
                        >
                          Delete
                        </button>
                      )}
                  </div>
                  <Link
                    href="/dashboard/accounting/bills"
                    className="text-sm text-slate-500 hover:text-slate-700"
                  >
                    Close
                  </Link>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
      <ConfirmModal
        open={confirmDeleteOpen}
        title="Delete unpaid bill?"
        description={openBill ? `Bill ${openBill.bill_number || openBill.id} will be hidden and its accrual will be reversed. The accounting audit trail remains.` : ""}
        confirmLabel="Delete bill"
        busy={deleting}
        danger
        onCancel={() => setConfirmDeleteOpen(false)}
        onConfirm={submitDelete}
      />
      <ConfirmModal
        open={confirmReverseOpen}
        title="Reverse bill?"
        description={openBill ? `Bill ${openBill.bill_number || openBill.id} will be reversed with a reversing accounting entry. This cannot be undone.` : ""}
        confirmLabel="Reverse bill"
        danger
        onCancel={() => setConfirmReverseOpen(false)}
        onConfirm={submitReverse}
      />
    </div>
  );
}