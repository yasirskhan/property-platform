// ============================================================
// New Deposit page
// ------------------------------------------------------------
// Route: /dashboard/accounting/deposits/new
//
// Pick a bank account and deposit date, then tick the
// un-deposited receipts that go in this deposit. All / None
// quick-select. Total is computed live.
//
// On submit, POSTs and redirects back to the deposits list.
// No GL posting — deposits tag receipts as deposited.
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  listUndepositedReceipts,
  createDeposit,
  UndepositedReceiptRow,
} from "@/lib/deposits";
import { listGLAccounts, GLAccount } from "@/lib/glAccounts";

export default function NewDepositPage() {
  const router = useRouter();

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Reference data
  const [cashAccounts, setCashAccounts] = useState<
    Array<{ id: number; gl_number: string; name: string }>
  >([]);

  // Form fields
  const [bankAccountId, setBankAccountId] = useState<number | "">("");
  const [depositDate, setDepositDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [depositNumber, setDepositNumber] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");

  // Receipts
  const [rows, setRows] = useState<
    Array<UndepositedReceiptRow & { include: boolean }>
  >([]);

  // Load cash accounts once
  useEffect(() => {
    (async () => {
      try {
        const accts = await listGLAccounts(false);
        const flat: GLAccount[] = [];
        for (const g of accts.groups) flat.push(...g.accounts);

        const cash = flat.filter(
          (a) =>
            a.is_active &&
            (a.account_type === "ASSET" ||
              a.gl_number === "1150" ||
              a.gl_number === "1160")
        );

        const mapped = cash.map((a) => ({
          id: a.id,
          gl_number: a.gl_number,
          name: a.name,
        }));
        setCashAccounts(mapped);

        const rent = cash.find((a) => a.gl_number === "1150");
        if (rent) setBankAccountId(rent.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load accounts");
      }
    })();
  }, []);

  // Reload undeposited receipts when bank account changes
  useEffect(() => {
    if (!bankAccountId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await listUndepositedReceipts(Number(bankAccountId));
        if (cancelled) return;
        setRows(
          data.items.map((it) => ({ ...it, include: true }))
        );
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load receipts");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [bankAccountId]);

  const includedRows = rows.filter((r) => r.include);
  const total = includedRows.reduce(
    (sum, r) => sum + Number(r.amount || 0),
    0
  );

  function toggleRow(id: number) {
    setRows((prev) =>
      prev.map((r) => (r.id === id ? { ...r, include: !r.include } : r))
    );
  }

  function selectAll() {
    setRows((prev) => prev.map((r) => ({ ...r, include: true })));
  }

  function selectNone() {
    setRows((prev) => prev.map((r) => ({ ...r, include: false })));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!bankAccountId) {
      setError("Pick a bank account.");
      return;
    }
    if (includedRows.length === 0) {
      setError("Select at least one receipt to deposit.");
      return;
    }

    setSubmitting(true);
    try {
      await createDeposit({
        bank_gl_account_id: Number(bankAccountId),
        deposit_date: depositDate,
        deposit_number: depositNumber || null,
        description: description || null,
        notes: notes || null,
        receipt_ids: includedRows.map((r) => r.id),
      });
      router.push(`/dashboard/accounting/deposits`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create deposit");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <Link
          href="/dashboard/accounting/deposits"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Deposits
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">
          New Deposit
        </h1>
      </div>

      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Header fields */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Bank account *
            </label>
            <select
              required
              value={bankAccountId}
              onChange={(e) =>
                setBankAccountId(e.target.value ? Number(e.target.value) : "")
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
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Deposit date *
            </label>
            <input
              type="date"
              required
              value={depositDate}
              onChange={(e) => setDepositDate(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Deposit #
            </label>
            <input
              type="text"
              value={depositNumber}
              onChange={(e) => setDepositNumber(e.target.value)}
              placeholder="Leave blank to auto-number"
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Notes</label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Receipt picker */}
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold text-slate-700">
              Un-deposited receipts ({rows.length})
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={selectAll}
                className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded"
              >
                All
              </button>
              <button
                type="button"
                onClick={selectNone}
                className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded"
              >
                None
              </button>
            </div>
          </div>

          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-center px-2 py-2 font-medium text-slate-700 w-10">
                  ✓
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-20">
                  ID
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Date
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-24">
                  Type
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  From
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Reference
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-28">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-6 text-center text-slate-500 text-xs"
                  >
                    Loading receipts…
                  </td>
                </tr>
              )}
              {!loading && rows.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-6 text-center text-slate-500 text-xs"
                  >
                    No un-deposited receipts for this bank account.
                  </td>
                </tr>
              )}
              {!loading &&
                rows.map((r) => (
                  <tr
                    key={r.id}
                    className={`border-t border-slate-100 ${
                      r.include ? "bg-slate-50/40" : ""
                    }`}
                  >
                    <td className="px-2 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={r.include}
                        onChange={() => toggleRow(r.id)}
                      />
                    </td>
                    <td className="px-3 py-2 text-slate-500 font-mono">
                      #{r.id}
                    </td>
                    <td className="px-3 py-2 text-slate-700">
                      {r.receipt_date}
                    </td>
                    <td className="px-3 py-2 text-slate-700">
                      <span className="text-xs px-2 py-0.5 bg-slate-100 rounded">
                        {r.type}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-700">
                      {r.payer_label || "—"}
                    </td>
                    <td className="px-3 py-2 text-slate-500 text-xs">
                      {r.reference_number || "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {Number(r.amount).toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </td>
                  </tr>
                ))}
            </tbody>
            {rows.length > 0 && (
              <tfoot>
                <tr className="border-t border-slate-200 bg-slate-50">
                  <td
                    colSpan={5}
                    className="px-3 py-2 text-right font-medium text-slate-700"
                  >
                    Selected: {includedRows.length} of {rows.length}
                  </td>
                  <td className="px-3 py-2 text-right font-medium text-slate-700">
                    Total
                  </td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">
                    {total.toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting || includedRows.length === 0}
            className="text-sm px-5 py-2.5 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? "Creating…" : `Make Deposit (${includedRows.length})`}
          </button>
          <Link
            href="/dashboard/accounting/deposits"
            className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}