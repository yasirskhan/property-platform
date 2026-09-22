// ============================================================
// New Journal Entry page
// ------------------------------------------------------------
// Manual balanced multi-line JE. Live balance check.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";
import { formatMoney } from "@/lib/money";

interface Property {
  id: number;
  name: string;
}

interface GLAccount {
  id: number;
  gl_number: string;
  name: string;
  account_type: string;
}

interface LineRow {
  key: string;
  gl_account_id: number | "";
  property_id: number | "";
  description: string;
  debit: string;
  credit: string;
}

export default function NewJournalEntryPage() {
  const router = useRouter();

  const [properties, setProperties] = useState<Property[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [transactionDate, setTransactionDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [referenceNumber, setReferenceNumber] = useState("");
  const [memo, setMemo] = useState("");

  let rowCounter = 0;
  function newRow(): LineRow {
    rowCounter += 1;
    return {
      key: `row-${Date.now()}-${rowCounter}`,
      gl_account_id: "",
      property_id: "",
      description: "",
      debit: "",
      credit: "",
    };
  }

  const [lines, setLines] = useState<LineRow[]>(() => [newRow(), newRow()]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [props, gls] = await Promise.all([
          apiGet("/properties"),
          apiGet("/api/accounting/gl-accounts"),
        ]);

        if (cancelled) return;

        setProperties(props as Property[]);

        const groups = (gls as {
          groups: { account_type: string; accounts: GLAccount[] }[];
        }).groups;
        const all = groups.flatMap((g) => g.accounts);
        setAccounts(all);
      } catch (e: unknown) {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : "Could not load form data."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  function addRow() {
    setLines((prev) => [...prev, newRow()]);
  }

  function removeRow(key: string) {
    setLines((prev) => (prev.length <= 2 ? prev : prev.filter((r) => r.key !== key)));
  }

  function updateRow(key: string, patch: Partial<LineRow>) {
    setLines((prev) =>
      prev.map((r) => (r.key === key ? { ...r, ...patch } : r))
    );
  }

  const totalDebit = lines.reduce(
    (acc, r) => acc + (parseFloat(r.debit) || 0),
    0
  );
  const totalCredit = lines.reduce(
    (acc, r) => acc + (parseFloat(r.credit) || 0),
    0
  );
  const diff = totalDebit - totalCredit;
  const balanced = Math.abs(diff) < 0.01;

  async function submit() {
    const validLines = lines.filter(
      (r) =>
        r.gl_account_id &&
        (parseFloat(r.debit) > 0 || parseFloat(r.credit) > 0)
    );
    if (validLines.length < 2) {
      setError("At least 2 lines are required.");
      return;
    }
    if (!balanced) {
      setError(
        `Journal entry does not balance (debits ${formatMoney(
          totalDebit.toFixed(2)
        )} vs credits ${formatMoney(totalCredit.toFixed(2))}).`
      );
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await apiPost("/api/accounting/journal-entries", {
        transaction_date: transactionDate,
        reference_number: referenceNumber || null,
        memo: memo || null,
        lines: validLines.map((r) => ({
          gl_account_id: r.gl_account_id,
          property_id: r.property_id || null,
          description: r.description || null,
          debit: parseFloat(r.debit) || 0,
          credit: parseFloat(r.credit) || 0,
        })),
      });
      router.push(
        `/dashboard/accounting/journal-entries/${(created as { id: number }).id}`
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not save journal entry.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto p-6 text-slate-500">Loading...</div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="text-xl font-semibold text-slate-900 mb-1">
        New Journal Entry
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        Manual balanced entry. Debits must equal credits.
      </p>

      {error && (
        <div className="text-sm text-red-600 mb-4 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-5 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Transaction date <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Reference #
            </label>
            <input
              type="text"
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">Memo</label>
            <input
              type="text"
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-5">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Account</th>
              <th className="text-left px-3 py-2 font-medium">Property</th>
              <th className="text-left px-3 py-2 font-medium">Description</th>
              <th className="text-right px-3 py-2 font-medium">Debit</th>
              <th className="text-right px-3 py-2 font-medium">Credit</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lines.map((r) => (
              <tr key={r.key} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  <select
                    value={r.gl_account_id}
                    onChange={(e) =>
                      updateRow(r.key, {
                        gl_account_id: e.target.value
                          ? Number(e.target.value)
                          : "",
                      })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white"
                  >
                    <option value="">Select account...</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.gl_number} {a.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <select
                    value={r.property_id}
                    onChange={(e) =>
                      updateRow(r.key, {
                        property_id: e.target.value
                          ? Number(e.target.value)
                          : "",
                      })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white"
                  >
                    <option value="">(none)</option>
                    {properties.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <input
                    type="text"
                    value={r.description}
                    onChange={(e) =>
                      updateRow(r.key, { description: e.target.value })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={r.debit}
                    onChange={(e) =>
                      updateRow(r.key, { debit: e.target.value, credit: "" })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm text-right"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={r.credit}
                    onChange={(e) =>
                      updateRow(r.key, { credit: e.target.value, debit: "" })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm text-right"
                  />
                </td>
                <td className="px-2 py-2">
                  <button
                    type="button"
                    onClick={() => removeRow(r.key)}
                    disabled={lines.length <= 2}
                    className="text-xs text-slate-400 hover:text-red-600 disabled:opacity-30"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-slate-50">
            <tr className="border-t border-slate-200">
              <td colSpan={3} className="px-3 py-2 text-xs text-slate-500">
                <button
                  type="button"
                  onClick={addRow}
                  className="text-blue-600 hover:underline"
                >
                  + Add line
                </button>
              </td>
              <td className="px-3 py-2 text-right font-mono font-medium">
                {formatMoney(totalDebit.toFixed(2))}
              </td>
              <td className="px-3 py-2 text-right font-mono font-medium">
                {formatMoney(totalCredit.toFixed(2))}
              </td>
              <td />
            </tr>
            <tr>
              <td colSpan={5} className="px-3 py-2 text-right text-xs">
                {balanced ? (
                  <span className="text-green-600 font-medium">Balanced</span>
                ) : (
                  <span className="text-red-600 font-medium">
                    Off by {formatMoney(Math.abs(diff).toFixed(2))}
                  </span>
                )}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => router.push("/dashboard/accounting/journal-entries")}
          className="px-4 py-2 rounded-md border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={saving || !balanced}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save journal entry"}
        </button>
      </div>
    </div>
  );
}