// ============================================================
// Bills list page
// ------------------------------------------------------------
// Route: /dashboard/accounting/bills
//
// Shows every bill in the current org. Filters: date range,
// status, payee. Clicking a row opens a CENTERED modal with
// the bill detail + actions (Pay / Reverse).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listBills,
  Bill,
  BillList,
  BILL_STATUS_LABELS,
  BILL_STATUS_COLORS,
} from "@/lib/bills";
import { apiGet } from "@/lib/api";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function BillsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<BillList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [status, setStatus] = useState<"" | "UNPAID" | "PARTIAL" | "PAID" | "VOID">("");
  const [payeeName, setPayeeName] = useState("");
  const [includeReversed, setIncludeReversed] = useState(true);

  // Selected bill for the modal
  const [selected, setSelected] = useState<Bill | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listBills({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        status: status || undefined,
        payee_name: payeeName || undefined,
        include_reversed: includeReversed,
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
  }, [dateFrom, dateTo, status, payeeName, includeReversed]);

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  const canWrite = me ? WRITE_ROLES.includes(me.role) : false;

  const totalUnpaid = data.items
    .filter((b) => !b.is_reversed && b.status !== "PAID" && b.status !== "VOID")
    .reduce(
      (sum, b) => sum + (Number(b.amount) - Number(b.amount_paid || 0)),
      0
    );

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Bills</h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "bill" : "bills"}
            {" · "}
            Outstanding:{" "}
            {totalUnpaid.toLocaleString("en-US", {
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
            href="/dashboard/accounting/trial-balance"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Trial Balance
          </Link>
          {canWrite && (
            <Link
              href="/dashboard/accounting/bills/new"
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + Enter Bill
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
        <div>
          <label className="block text-xs text-slate-500 mb-1">Status</label>
          <select
            value={status}
            onChange={(e) =>
              setStatus(e.target.value as "" | "UNPAID" | "PARTIAL" | "PAID" | "VOID")
            }
            className="border border-slate-300 rounded px-2 py-1.5 text-sm"
          >
            <option value="">All statuses</option>
            <option value="UNPAID">Unpaid</option>
            <option value="PARTIAL">Partial</option>
            <option value="PAID">Paid</option>
            <option value="VOID">Void</option>
          </select>
        </div>
        <div className="flex-1 min-w-[180px]">
          <label className="block text-xs text-slate-500 mb-1">Payee</label>
          <input
            type="text"
            value={payeeName}
            onChange={(e) => setPayeeName(e.target.value)}
            placeholder="Search by payee name"
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 pb-1.5">
          <input
            type="checkbox"
            checked={includeReversed}
            onChange={(e) => setIncludeReversed(e.target.checked)}
          />
          Show reversed
        </label>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-24">
                Bill #
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Date
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Due
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Payee
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Status
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Amount
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Balance
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No bills yet.
                </td>
              </tr>
            )}
            {data.items.map((b) => {
              const balance = Number(b.amount) - Number(b.amount_paid || 0);
              return (
                <tr
                  key={b.id}
                  onClick={() => setSelected(b)}
                  className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer ${
                    b.is_reversed ? "opacity-60" : ""
                  }`}
                >
                  <td className="px-4 py-2 text-slate-500 font-mono">
                    {b.bill_number || `#${b.id}`}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{b.bill_date}</td>
                  <td className="px-4 py-2 text-slate-700">{b.due_date || "—"}</td>
                  <td
                    className={`px-4 py-2 ${
                      b.is_reversed
                        ? "line-through text-slate-400"
                        : "text-slate-800"
                    }`}
                  >
                    {b.payee_name}
                    {b.is_reversed && (
                      <span className="ml-2 text-xs text-red-600">reversed</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        BILL_STATUS_COLORS[b.status] || "bg-slate-100"
                      }`}
                    >
                      {BILL_STATUS_LABELS[b.status] || b.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {Number(b.amount).toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600">
                    {balance > 0
                      ? balance.toLocaleString("en-US", {
                          style: "currency",
                          currency: "USD",
                        })
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Centered modal */}
      {selected && (
        <BillDetailPanel
          bill={selected}
          canWrite={canWrite}
          onClose={() => setSelected(null)}
          onChanged={async () => {
            await load();
            setSelected(null);
          }}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Centered modal: bill detail + actions
// ------------------------------------------------------------
function BillDetailPanel({
  bill,
  canWrite,
  onClose,
  onChanged,
}: {
  bill: Bill;
  canWrite: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [lines, setLines] = useState<
    Array<{
      id: number;
      gl_account_number: string | null;
      gl_account_name: string | null;
      description: string | null;
      amount: string;
    }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  // Pay form state
  const [showPayForm, setShowPayForm] = useState(false);
  const [payAmount, setPayAmount] = useState("");
  const [payDate, setPayDate] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [cashAccountId, setCashAccountId] = useState<number | "">("");
  const [cashAccounts, setCashAccounts] = useState<
    Array<{ id: number; gl_number: string; name: string }>
  >([]);
  const [payRef, setPayRef] = useState("");
  const [payRemarks, setPayRemarks] = useState("");
  const [paying, setPaying] = useState(false);

  const outstanding = Number(bill.amount) - Number(bill.amount_paid || 0);

  // Load lines + cash accounts
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const { getBill } = await import("@/lib/bills");
        const detail = await getBill(bill.id);
        if (!cancelled) setLines(detail.lines);
      } finally {
        if (!cancelled) setLoading(false);
      }

      try {
        const { listGLAccounts } = await import("@/lib/glAccounts");
        const accts = await listGLAccounts(false);
        const flat: Array<{
          id: number;
          gl_number: string;
          name: string;
          account_type: string;
          is_active: boolean;
        }> = [];
        for (const g of accts.groups) flat.push(...g.accounts);

        const cash = flat.filter(
          (a) =>
            a.is_active &&
            (a.account_type === "ASSET" ||
              a.gl_number === "1150" ||
              a.gl_number === "1160")
        );
        if (!cancelled) {
          setCashAccounts(
            cash.map((a) => ({
              id: a.id,
              gl_number: a.gl_number,
              name: a.name,
            }))
          );
          const rent = cash.find((a) => a.gl_number === "1150");
          if (rent) setCashAccountId(rent.id);
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [bill.id]);

  useEffect(() => {
    if (showPayForm) {
      setPayAmount(outstanding.toFixed(2));
    }
  }, [showPayForm, outstanding]);

  async function submitPayment(e: React.FormEvent) {
    e.preventDefault();
    setErr("");

    const amt = Number(payAmount);
    if (!amt || amt <= 0) {
      setErr("Enter a payment amount greater than zero.");
      return;
    }
    if (!cashAccountId) {
      setErr("Pick a cash account.");
      return;
    }

    setPaying(true);
    try {
      const { payBill } = await import("@/lib/bills");
      await payBill(bill.id, {
        payment_date: payDate,
        cash_gl_account_id: Number(cashAccountId),
        amount: amt,
        reference_number: payRef || null,
        remarks: payRemarks || null,
      });
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Payment failed");
    } finally {
      setPaying(false);
    }
  }

  return (
    <>
      {/* Dark backdrop — click to close */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
      />

      {/* Centered modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="w-full max-w-2xl max-h-[90vh] bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
            <div>
              <div className="text-xs text-slate-500">Bill</div>
              <div className="font-semibold text-slate-900 text-lg">
                {bill.bill_number || `#${bill.id}`}
                <span
                  className={`ml-2 text-xs px-2 py-0.5 rounded ${
                    BILL_STATUS_COLORS[bill.status] || "bg-slate-100"
                  }`}
                >
                  {BILL_STATUS_LABELS[bill.status]}
                </span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-700 text-2xl leading-none"
            >
              ×
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 text-sm">
            {err && (
              <div className="px-3 py-2 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
                {err}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Payee</div>
                <div className="text-slate-800">{bill.payee_name}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Reference</div>
                <div className="text-slate-800">{bill.reference_number || "—"}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Bill date</div>
                <div className="text-slate-800">{bill.bill_date}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Due</div>
                <div className="text-slate-800">{bill.due_date || "—"}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Amount</div>
                <div className="text-slate-800 font-mono text-lg">
                  {Number(bill.amount).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Balance</div>
                <div className="text-slate-800 font-mono text-lg">
                  {outstanding > 0
                    ? outstanding.toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })
                    : "—"}
                </div>
              </div>
            </div>

            {bill.remarks && (
              <div>
                <div className="text-xs text-slate-500">Remarks</div>
                <div className="text-slate-800 whitespace-pre-wrap">
                  {bill.remarks}
                </div>
              </div>
            )}

            {bill.gl_transaction_id && (
              <div>
                <div className="text-xs text-slate-500">GL Transaction</div>
                <Link
                  href={`/dashboard/accounting/journal-entries/${bill.gl_transaction_id}`}
                  className="text-blue-600 hover:underline"
                >
                  #{bill.gl_transaction_id}
                </Link>
              </div>
            )}

            <div className="pt-4 border-t border-slate-200">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                Lines
              </div>
              {loading ? (
                <div className="text-slate-500 text-xs">Loading…</div>
              ) : lines.length === 0 ? (
                <div className="text-slate-500 text-xs">No lines.</div>
              ) : (
                <ul className="space-y-2">
                  {lines.map((ln) => (
                    <li
                      key={ln.id}
                      className="flex items-start justify-between text-xs border-b border-slate-100 pb-2"
                    >
                      <div>
                        <div className="text-slate-700">
                          {ln.gl_account_number} {ln.gl_account_name}
                        </div>
                        {ln.description && (
                          <div className="text-slate-500">{ln.description}</div>
                        )}
                      </div>
                      <div className="font-mono text-slate-800">
                        {Number(ln.amount).toLocaleString("en-US", {
                          style: "currency",
                          currency: "USD",
                        })}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Inline Pay form */}
            {showPayForm && (
              <div className="pt-4 border-t border-slate-200">
                <div className="text-xs font-semibold text-slate-500 uppercase mb-3">
                  Pay this bill
                </div>
                <form onSubmit={submitPayment} className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">
                        Payment amount *
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        required
                        value={payAmount}
                        onChange={(e) => setPayAmount(e.target.value)}
                        className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono"
                      />
                      <div className="text-xs text-slate-400 mt-1">
                        Outstanding: ${outstanding.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">
                        Payment date *
                      </label>
                      <input
                        type="date"
                        required
                        value={payDate}
                        onChange={(e) => setPayDate(e.target.value)}
                        className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs text-slate-500 mb-1">
                      Cash account *
                    </label>
                    <select
                      required
                      value={cashAccountId}
                      onChange={(e) =>
                        setCashAccountId(
                          e.target.value ? Number(e.target.value) : ""
                        )
                      }
                      className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                    >
                      <option value="">— Select —</option>
                      {cashAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.gl_number} {a.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">
                        Reference #
                      </label>
                      <input
                        type="text"
                        value={payRef}
                        onChange={(e) => setPayRef(e.target.value)}
                        placeholder="Check #, ACH trace"
                        className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">
                        Remarks
                      </label>
                      <input
                        type="text"
                        value={payRemarks}
                        onChange={(e) => setPayRemarks(e.target.value)}
                        className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="submit"
                      disabled={paying}
                      className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
                    >
                      {paying ? "Paying…" : "Confirm Payment"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowPayForm(false)}
                      disabled={paying}
                      className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>

          {/* Footer actions */}
          {canWrite &&
            !bill.is_reversed &&
            bill.status !== "PAID" &&
            !showPayForm && (
              <div className="border-t border-slate-200 p-4 flex items-center gap-3">
                <button
                  onClick={() => setShowPayForm(true)}
                  className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
                >
                  Pay Bill
                </button>
                {bill.status === "UNPAID" && (
                  <button
                    onClick={async () => {
                      if (
                        !window.confirm(
                          `Reverse bill ${bill.bill_number || bill.id}?`
                        )
                      )
                        return;
                      setErr("");
                      try {
                        const { reverseBill } = await import("@/lib/bills");
                        await reverseBill(bill.id, {
                          reversal_date: new Date()
                            .toISOString()
                            .slice(0, 10),
                        });
                        onChanged();
                      } catch (e) {
                        setErr(
                          e instanceof Error ? e.message : "Reverse failed"
                        );
                      }
                    }}
                    className="text-sm px-4 py-2 text-red-600 hover:text-red-800"
                  >
                    Reverse
                  </button>
                )}
              </div>
            )}
        </div>
      </div>
    </>
  );
}