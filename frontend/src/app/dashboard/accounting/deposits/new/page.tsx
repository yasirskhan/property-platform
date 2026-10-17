// ============================================================
// New Bank Deposit page
// ------------------------------------------------------------
// Pick a bank account, pick un-deposited receipts, make deposit.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createDeposit,
  listUndepositedReceipts,
  type UndepositedReceiptRow,
} from "@/lib/deposits";
import { formatMoney, formatDate } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

interface BankAccount {
  id: number;
  name: string;
  gl_account_id: number;
  gl_account_number?: string | null;
  gl_account_name?: string | null;
}

export default function NewDepositPage() {
  const router = useRouter();
  const { prefs } = useDisplay();

  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [bankAccountId, setBankAccountId] = useState<number | "">("");
  const [receipts, setReceipts] = useState<UndepositedReceiptRow[]>([]);
  const [included, setIncluded] = useState<Set<number>>(new Set());
  const [depositDate, setDepositDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [depositNumber, setDepositNumber] = useState("");
  const [description, setDescription] = useState("");

  const [loading, setLoading] = useState(true);
  const [loadingReceipts, setLoadingReceipts] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/accounting/bank-accounts", {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => {
        const list = (d.items || []) as BankAccount[];
        setBankAccounts(list);
        if (list.length === 1) setBankAccountId(list[0].id);
      })
      .catch(() => setBankAccounts([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!bankAccountId) {
      setReceipts([]);
      setIncluded(new Set());
      return;
    }
    setLoadingReceipts(true);
    setError(null);
    const bank = bankAccounts.find((b) => b.id === bankAccountId);
    if (!bank) {
      setLoadingReceipts(false);
      return;
    }
    listUndepositedReceipts(bank.gl_account_id)
      .then((d) => {
        setReceipts(d.items);
        setIncluded(new Set(d.items.map((r) => r.id)));
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load receipts.")
      )
      .finally(() => setLoadingReceipts(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bankAccountId]);

  function toggle(id: number) {
    setIncluded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setIncluded(new Set(receipts.map((r) => r.id)));
  }

  function selectNone() {
    setIncluded(new Set());
  }

  const includedRows = receipts.filter((r) => included.has(r.id));
  const total = includedRows.reduce((acc, r) => acc + parseFloat(r.amount), 0);
  const mismatchedReceiptDates = includedRows.filter(
    (r) => r.receipt_date !== depositDate
  );

  async function submit() {
    if (!bankAccountId) {
      setError("Pick a bank account.");
      return;
    }
    if (includedRows.length === 0) {
      setError("Include at least one receipt.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await createDeposit({
        bank_gl_account_id:
          bankAccounts.find((b) => b.id === bankAccountId)!.gl_account_id,
        deposit_date: depositDate,
        deposit_number: depositNumber || null,
        description: description || null,
        receipt_ids: includedRows.map((r) => r.id),
      });
      router.push(`/dashboard/accounting/deposits?highlight=${created.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not create deposit.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6 text-slate-500">Loading...</div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6" data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()} data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}>
      <h1 className="text-xl font-semibold text-slate-900 mb-1">
        New Bank Deposit
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        Group un-deposited receipts into a batch for the bank.
      </p>
      <span hidden aria-hidden="true" data-compat-slot="deposits.bank-specific-numbering" />

      {error && (
        <div className="text-sm text-red-600 mb-4 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {mismatchedReceiptDates.length > 0 && (
        <div className="text-sm text-amber-800 mb-4 bg-amber-50 border border-amber-200 rounded-md px-3 py-2" role="status">
          {mismatchedReceiptDates.length} selected {mismatchedReceiptDates.length === 1 ? "receipt has" : "receipts have"} a date different from the deposit date. Review the dates before creating the deposit.
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-5 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Bank account <span className="text-red-500">*</span>
            </label>
            <select
              value={bankAccountId}
              onChange={(e) =>
                setBankAccountId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
            >
              <option value="">Select bank account...</option>
              {bankAccounts.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Deposit date <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={depositDate}
              onChange={(e) => setDepositDate(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Deposit #
            </label>
            <input
              type="text"
              value={depositNumber}
              onChange={(e) => setDepositNumber(e.target.value)}
              placeholder="auto"
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-5">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
          <div className="text-sm font-medium text-slate-700">
            Available receipts
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={selectAll}
              disabled={receipts.length === 0}
              className="text-xs text-blue-600 hover:underline disabled:opacity-40"
            >
              All
            </button>
            <button
              type="button"
              onClick={selectNone}
              disabled={receipts.length === 0}
              className="text-xs text-blue-600 hover:underline disabled:opacity-40"
            >
              None
            </button>
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-2 w-8" />
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Type</th>
              <th className="text-left px-4 py-2 font-medium">Payer</th>
              <th className="text-left px-4 py-2 font-medium">Reference</th>
              <th className="text-right px-4 py-2 font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {!bankAccountId && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Pick a bank account above.
                </td>
              </tr>
            )}
            {bankAccountId && loadingReceipts && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Loading receipts...
                </td>
              </tr>
            )}
            {bankAccountId && !loadingReceipts && receipts.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No un-deposited receipts for this bank account.
                </td>
              </tr>
            )}
            {receipts.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={included.has(r.id)}
                    onChange={() => toggle(r.id)}
                  />
                </td>
                <td className="px-4 py-2">{formatDate(r.receipt_date)}</td>
                <td className="px-4 py-2">{r.type}</td>
                <td className="px-4 py-2 text-slate-500">
                  {r.payer_label || "—"}
                </td>
                <td className="px-4 py-2 text-slate-500">
                  {r.reference_number || "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(r.amount)}
                </td>
              </tr>
            ))}
          </tbody>
          {receipts.length > 0 && (
            <tfoot className="bg-slate-50 text-slate-700">
              <tr className="border-t border-slate-200">
                <td colSpan={5} className="px-4 py-2 text-xs">
                  {includedRows.length} of {receipts.length} receipts
                </td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(total.toFixed(2))}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => router.push("/dashboard/accounting/deposits")}
          className="px-4 py-2 rounded-md border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={submitting || includedRows.length === 0}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Creating…" : `Make Deposit (${includedRows.length})`}
        </button>
      </div>
    </div>
  );
}