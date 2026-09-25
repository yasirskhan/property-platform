"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import {
  createBankAdjustment,
  listBankAdjustments,
  reverseBankAdjustment,
  type BankAdjustment,
} from "@/lib/bankAdjustments";
import { getBankAccount, type BankAccount } from "@/lib/bankAccounts";
import { listGLAccounts, type GLAccount } from "@/lib/glAccounts";
import { formatDate, formatMoney } from "@/lib/money";

type Direction = "INCREASE" | "DECREASE";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function BankAdjustmentsPage() {
  const bankId = Number(useParams().id);
  const [bank, setBank] = useState<BankAccount | null>(null);
  const [adjustments, setAdjustments] = useState<BankAdjustment[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const [adjustmentDate, setAdjustmentDate] = useState(today());
  const [direction, setDirection] = useState<Direction>("DECREASE");
  const [amount, setAmount] = useState("");
  const [offsetId, setOffsetId] = useState("");
  const [reference, setReference] = useState("");
  const [memo, setMemo] = useState("");
  const [reversalDate, setReversalDate] = useState(today());

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      getBankAccount(bankId),
      listBankAdjustments(bankId),
      listGLAccounts(false),
    ])
      .then(([bankRow, adjustmentRows, glRows]) => {
        if (!active) return;
        setBank(bankRow);
        setAdjustments(adjustmentRows.items);
        setAccounts(glRows.groups.flatMap((group) => group.accounts));
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Could not load adjustments.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [bankId]);

  const offsetAccounts = useMemo(
    () =>
      accounts.filter(
        (account) =>
          account.is_active &&
          (!bank || account.id !== bank.gl_account_id)
      ),
    [accounts, bank]
  );

  async function refreshAdjustments() {
    const rows = await listBankAdjustments(bankId);
    setAdjustments(rows.items);
  }

  async function submitAdjustment() {
    setError("");
    setInfo("");
    if (!amount || Number(amount) <= 0) {
      setError("Enter an amount greater than zero.");
      return;
    }
    if (!offsetId) {
      setError("Choose an offset GL account.");
      return;
    }

    setSaving(true);
    try {
      await createBankAdjustment(bankId, {
        adjustment_date: adjustmentDate,
        direction,
        amount,
        offset_gl_account_id: Number(offsetId),
        reference_number: reference.trim() || null,
        memo: memo.trim() || null,
      });
      await refreshAdjustments();
      setAmount("");
      setReference("");
      setMemo("");
      setInfo("Bank adjustment posted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not post adjustment.");
    } finally {
      setSaving(false);
    }
  }

  async function reverse(row: BankAdjustment) {
    if (row.is_reversed) return;
    if (!window.confirm("Reverse this bank adjustment? The original entry will remain in the ledger.")) {
      return;
    }
    setSaving(true);
    setError("");
    setInfo("");
    try {
      await reverseBankAdjustment(bankId, row.id, {
        reversal_date: reversalDate,
        memo: `Reversal of bank adjustment #${row.id}`,
      });
      await refreshAdjustments();
      setInfo("Bank adjustment reversed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reverse adjustment.");
    } finally {
      setSaving(false);
    }
  }

  if (loading && !bank) {
    return <div className="p-6 text-slate-500">Loading…</div>;
  }

  if (!bank) {
    return (
      <div className="p-6">
        <Link
          href="/dashboard/accounting/bank-accounts"
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          ← Bank Accounts
        </Link>
        <p className="mt-4 text-red-600">{error || "Bank account not found."}</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl">
      <div className="mb-4">
        <Link
          href="/dashboard/accounting/bank-accounts"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Bank Accounts
        </Link>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Bank Adjustments</h1>
          <p className="text-sm text-slate-500 mt-1">
            {bank.name} · {bank.gl_account_number} {bank.gl_account_name}
          </p>
        </div>
        <label className="text-xs text-slate-500">
          Reversal date
          <input
            type="date"
            value={reversalDate}
            onChange={(event) => setReversalDate(event.target.value)}
            className="block mt-1 border border-slate-300 rounded px-2 py-1.5 text-sm text-slate-800"
          />
        </label>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {info && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          {info}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
        <h2 className="font-semibold text-slate-900 mb-4">Post Adjustment</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="text-xs text-slate-500">
            Date
            <input
              type="date"
              value={adjustmentDate}
              onChange={(event) => setAdjustmentDate(event.target.value)}
              className="block w-full mt-1 border border-slate-300 rounded px-3 py-2 text-sm text-slate-800"
            />
          </label>
          <label className="text-xs text-slate-500">
            Direction
            <select
              value={direction}
              onChange={(event) => setDirection(event.target.value as Direction)}
              className="block w-full mt-1 border border-slate-300 rounded px-3 py-2 text-sm text-slate-800"
            >
              <option value="INCREASE">Increase bank balance</option>
              <option value="DECREASE">Decrease bank balance</option>
            </select>
          </label>
          <label className="text-xs text-slate-500">
            Amount
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              className="block w-full mt-1 border border-slate-300 rounded px-3 py-2 text-sm text-slate-800"
              placeholder="0.00"
            />
          </label>
          <label className="text-xs text-slate-500 md:col-span-2">
            Offset GL account
            <select
              value={offsetId}
              onChange={(event) => setOffsetId(event.target.value)}
              className="block w-full mt-1 border border-slate-300 rounded px-3 py-2 text-sm text-slate-800"
            >
              <option value="">Choose account…</option>
              {offsetAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.gl_number} · {account.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-500">
            Reference
            <input
              type="text"
              maxLength={40}
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              className="block w-full mt-1 border border-slate-300 rounded px-3 py-2 text-sm text-slate-800"
              placeholder="Optional"
            />
          </label>
          <label className="text-xs text-slate-500 md:col-span-3">
            Memo
            <textarea
              rows={2}
              maxLength={500}
              value={memo}
              onChange={(event) => setMemo(event.target.value)}
              className="block w-full mt-1 border border-slate-300 rounded px-3 py-2 text-sm text-slate-800"
              placeholder="Reason for the adjustment"
            />
          </label>
        </div>
        <div className="mt-4">
          <button
            type="button"
            disabled={saving}
            onClick={() => void submitAdjustment()}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Post Adjustment"}
          </button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200">
          <h2 className="font-semibold text-slate-900">Adjustment History</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Posted entries are immutable. Corrections are recorded as reversals.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Date</th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Direction</th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Offset</th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Reference</th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Memo</th>
                <th className="text-right px-4 py-2 font-medium text-slate-700">Amount</th>
                <th className="text-right px-4 py-2 font-medium text-slate-700">Status</th>
              </tr>
            </thead>
            <tbody>
              {adjustments.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    No bank adjustments posted.
                  </td>
                </tr>
              )}
              {adjustments.map((row) => (
                <tr key={row.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">{formatDate(row.transaction_date)}</td>
                  <td className="px-4 py-2">
                    {row.direction === "INCREASE" ? "Increase" : "Decrease"}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {row.offset_gl_account_number} {row.offset_gl_account_name}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{row.reference_number || "—"}</td>
                  <td className="px-4 py-2 text-slate-600">{row.memo || "—"}</td>
                  <td className="px-4 py-2 text-right font-medium">
                    {formatMoney(row.amount)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {row.is_reversed ? (
                      <span className="text-xs text-slate-500">Reversed</span>
                    ) : (
                      <button
                        type="button"
                        disabled={saving}
                        onClick={() => void reverse(row)}
                        className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                      >
                        Reverse
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
