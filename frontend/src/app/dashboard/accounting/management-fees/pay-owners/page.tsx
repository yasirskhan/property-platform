"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { listBankAccounts, type BankAccount } from "@/lib/bankAccounts";
import { formatDate, formatMoney } from "@/lib/money";
import {
  confirmOwnerPayoutBatch,
  createOwnerPayoutDraft,
  listOwnerPayouts,
  previewOwnerPayouts,
  type OwnerPayout,
  type OwnerPayoutDraft,
  type OwnerPayoutPreview,
} from "@/lib/ownerPayouts";
import { useDisplay } from "@/contexts/DisplayContext";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function PayOwnersPage() {
  const { prefs } = useDisplay();
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [bankId, setBankId] = useState<number | "">("");
  const [effectiveDate, setEffectiveDate] = useState(todayIso());
  const [preview, setPreview] = useState<OwnerPayoutPreview | null>(null);
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [history, setHistory] = useState<OwnerPayout[]>([]);
  const [result, setResult] = useState<OwnerPayoutDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [bankData, payoutData] = await Promise.all([
          listBankAccounts(false),
          listOwnerPayouts(25),
        ]);
        const operating = bankData.items.filter(
          (bank) => bank.account_type === "OPERATING"
        );
        setBanks(operating);
        setBankId(operating[0]?.id ?? "");
        setHistory(payoutData.items);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Could not load Pay Owners.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function loadPreview() {
    if (!bankId) {
      setError("Select an operating bank account.");
      return;
    }
    setPreviewing(true);
    setError(null);
    setResult(null);
    try {
      const data = await previewOwnerPayouts(bankId);
      setPreview(data);
      const nextAmounts: Record<number, string> = {};
      for (const owner of data.candidates) {
        nextAmounts[owner.owner_id] = owner.available_balance;
      }
      setAmounts(nextAmounts);
      setSelected({});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not preview payouts.");
    } finally {
      setPreviewing(false);
    }
  }

  function selectAllPayable() {
    if (!preview) return;
    const next: Record<number, boolean> = {};
    for (const owner of preview.candidates) {
      if (owner.can_pay) next[owner.owner_id] = true;
    }
    setSelected(next);
  }

  const chosen = useMemo(() => {
    if (!preview) return [];
    return preview.candidates
      .filter((owner) => selected[owner.owner_id] && owner.can_pay)
      .map((owner) => ({
        owner_id: owner.owner_id,
        amount: amounts[owner.owner_id] || "0",
      }))
      .filter((entry) => Number(entry.amount) > 0);
  }, [preview, selected, amounts]);

  const chosenTotal = useMemo(
    () => chosen.reduce((sum, row) => sum + Number(row.amount || 0), 0),
    [chosen]
  );

  async function confirmBatch(batchReference: string) {
    const accepted = window.confirm(
      "Confirm this batch was paid outside the app? This records the payout in accounting. The app does not move funds."
    );
    if (!accepted) return;
    setSaving(true);
    setError(null);
    try {
      await confirmOwnerPayoutBatch(batchReference, todayIso());
      const payoutData = await listOwnerPayouts(25);
      setHistory(payoutData.items);
      if (bankId) await loadPreview();
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "Could not record external payment."
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveDraft() {
    if (!bankId || chosen.length === 0) {
      setError("Select at least one payable owner.");
      return;
    }
    setSaving(true);
    setError(null);
    setResult(null);
    try {
      const created = await createOwnerPayoutDraft({
        bank_account_id: bankId,
        effective_date: effectiveDate,
        payouts: chosen,
      });
      setResult(created);
      const payoutData = await listOwnerPayouts(25);
      setHistory(payoutData.items);
      await loadPreview();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not save payout draft.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="p-6 text-slate-500">Loading...</div>;
  }

  return (
    <div
      className="p-6"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <div className="mb-4">
        <Link
          href="/dashboard/accounting/management-fees"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Management Fees
        </Link>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Pay Owners</h1>
        <p className="mt-1 text-sm text-slate-500">
          Review positive owner balances and prepare a payout draft. Creating a
          draft does not move funds and does not post the general ledger.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-3 py-3 text-sm text-green-800">
          Draft {result.batch_reference} saved for{" "}
          {formatMoney(result.total_amount)} across {result.entry_count} owner
          {result.entry_count === 1 ? "" : "s"}. No funds were moved and no
          accounting entry was posted.
        </div>
      )}

      <div className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-slate-600">
              Source bank
            </label>
            <select
              value={bankId}
              onChange={(e) =>
                setBankId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="">Select bank...</option>
              {banks.map((bank) => (
                <option key={bank.id} value={bank.id}>
                  {bank.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600">
              Planned payout date
            </label>
            <input
              type="date"
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={loadPreview}
              disabled={previewing || !bankId}
              className="w-full rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {previewing ? "Loading..." : "Load owner balances"}
            </button>
          </div>
        </div>
      </div>

      {preview && (
        <div className="mb-6 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
            <div className="text-sm text-slate-700">
              Source book balance:{" "}
              <span className="font-mono font-semibold">
                {formatMoney(preview.book_balance)}
              </span>
            </div>
            <button
              type="button"
              onClick={selectAllPayable}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Select all payable
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-white text-slate-600">
              <tr>
                <th className="w-12 px-4 py-2"></th>
                <th className="px-4 py-2 text-left font-medium">Owner</th>
                <th className="px-4 py-2 text-left font-medium">ACH readiness</th>
                <th className="px-4 py-2 text-right font-medium">Available</th>
                <th className="w-44 px-4 py-2 text-right font-medium">Draft amount</th>
              </tr>
            </thead>
            <tbody>
              {preview.candidates.map((owner) => (
                <tr key={owner.owner_id} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <input
                      type="checkbox"
                      disabled={!owner.can_pay}
                      checked={Boolean(selected[owner.owner_id])}
                      onChange={(e) =>
                        setSelected((current) => ({
                          ...current,
                          [owner.owner_id]: e.target.checked,
                        }))
                      }
                    />
                  </td>
                  <td className="px-4 py-2">
                    <div className="font-medium text-slate-800">{owner.owner_name}</div>
                    <div className="text-xs text-slate-500">{owner.owner_email}</div>
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-600">
                    {owner.ach_enabled && owner.account_last4
                      ? "Configured ••••" + owner.account_last4
                      : owner.reason || "Not ready"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {formatMoney(owner.available_balance)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      max={owner.available_balance}
                      disabled={!owner.can_pay || !selected[owner.owner_id]}
                      value={amounts[owner.owner_id] ?? ""}
                      onChange={(e) =>
                        setAmounts((current) => ({
                          ...current,
                          [owner.owner_id]: e.target.value,
                        }))
                      }
                      className="w-32 rounded border border-slate-300 px-2 py-1 text-right font-mono disabled:bg-slate-50"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3">
            <div className="text-sm text-slate-700">
              Selected total:{" "}
              <span className="font-mono font-semibold">
                {formatMoney(chosenTotal.toFixed(2))}
              </span>
            </div>
            <button
              type="button"
              onClick={saveDraft}
              disabled={saving || chosen.length === 0}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Create payout draft"}
            </button>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="font-semibold text-slate-900">Recent payout drafts</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Date</th>
              <th className="px-4 py-2 text-left font-medium">Owner</th>
              <th className="px-4 py-2 text-left font-medium">Batch</th>
              <th className="px-4 py-2 text-left font-medium">Status</th>
              <th className="px-4 py-2 text-right font-medium">Amount</th>
              <th className="w-44 px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {history.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No payout drafts yet.
                </td>
              </tr>
            )}
            {history.map((payout) => (
              <tr key={payout.id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-600">
                  {formatDate(payout.effective_date)}
                </td>
                <td className="px-4 py-2">{payout.owner_name}</td>
                <td className="px-4 py-2 text-xs font-mono text-slate-500">
                  {payout.batch_reference}
                </td>
                <td className="px-4 py-2 text-xs text-slate-600">{payout.status}</td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(payout.amount)}
                </td>
                <td className="px-4 py-2 text-right">
                  {payout.status === "DRAFT" && (
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => confirmBatch(payout.batch_reference)}
                      className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                    >
                      Confirm externally paid
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
