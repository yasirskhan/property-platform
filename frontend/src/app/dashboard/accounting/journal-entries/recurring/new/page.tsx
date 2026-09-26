"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { createRecurringJournalEntry } from "@/lib/journalEntries";
import { formatMoney } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

type Property = { id: number; name: string };
type GLAccount = {
  id: number;
  gl_number: string;
  name: string;
  account_type: string;
};
type LineRow = {
  key: string;
  gl_account_id: number | "";
  property_id: number | "";
  description: string;
  debit: string;
  credit: string;
};

function freshRow(key: string): LineRow {
  return {
    key,
    gl_account_id: "",
    property_id: "",
    description: "",
    debit: "",
    credit: "",
  };
}

export default function NewRecurringJournalEntryPage() {
  const router = useRouter();
  const { prefs } = useDisplay();
  const today = new Date().toISOString().slice(0, 10);

  const [properties, setProperties] = useState<Property[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState("");
  const [dayOfMonth, setDayOfMonth] = useState(
    String(new Date().getDate())
  );
  const [referenceNumber, setReferenceNumber] = useState("");
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<LineRow[]>([
    freshRow("row-initial-1"),
    freshRow("row-initial-2"),
  ]);

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
        setAccounts(groups.flatMap((group) => group.accounts));
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load form data.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  function updateRow(key: string, patch: Partial<LineRow>) {
    setLines((current) =>
      current.map((row) => (row.key === key ? { ...row, ...patch } : row))
    );
  }

  function addRow() {
    setLines((current) => [
      ...current,
      freshRow(`row-${crypto.randomUUID()}`),
    ]);
  }

  function removeRow(key: string) {
    setLines((current) =>
      current.length <= 2 ? current : current.filter((row) => row.key !== key)
    );
  }

  const totalDebit = lines.reduce(
    (sum, row) => sum + (parseFloat(row.debit) || 0),
    0
  );
  const totalCredit = lines.reduce(
    (sum, row) => sum + (parseFloat(row.credit) || 0),
    0
  );
  const balanced = Math.abs(totalDebit - totalCredit) < 0.01;

  async function submit() {
    const validLines = lines.filter(
      (row) =>
        row.gl_account_id &&
        (parseFloat(row.debit) > 0 || parseFloat(row.credit) > 0)
    );
    const day = Number(dayOfMonth);
    if (!name.trim()) {
      setError("Schedule name is required.");
      return;
    }
    if (!Number.isInteger(day) || day < 1 || day > 31) {
      setError("Day of month must be between 1 and 31.");
      return;
    }
    if (validLines.length < 2) {
      setError("At least 2 posting lines are required.");
      return;
    }
    if (!balanced) {
      setError("Debits and credits must balance.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      await createRecurringJournalEntry({
        name: name.trim(),
        start_date: startDate,
        end_date: endDate || null,
        day_of_month: day,
        reference_number: referenceNumber || null,
        memo: memo || null,
        lines: validLines.map((row) => ({
          gl_account_id: Number(row.gl_account_id),
          property_id: row.property_id ? Number(row.property_id) : null,
          description: row.description || null,
          debit: parseFloat(row.debit) || 0,
          credit: parseFloat(row.credit) || 0,
        })),
      });
      router.push("/dashboard/accounting/journal-entries");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save recurring journal entry.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="max-w-5xl mx-auto p-6 text-slate-500">Loading…</div>;
  }

  return (
    <div
      className="max-w-5xl mx-auto p-6"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <button
        type="button"
        onClick={() => router.push("/dashboard/accounting/journal-entries")}
        className="text-sm text-slate-500 hover:text-slate-800 mb-4"
      >
        ← Back to Journal Entries
      </button>

      <h1 className="text-2xl font-bold text-slate-900">New Recurring Journal Entry</h1>
      <p className="text-sm text-slate-500 mt-1 mb-6">
        Posts a balanced journal entry automatically each month.
      </p>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-5">
          {error}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5 space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">
            Schedule name
          </label>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            placeholder="Monthly accrual"
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Start date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              End date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Day of month
            </label>
            <input
              type="number"
              min="1"
              max="31"
              value={dayOfMonth}
              onChange={(event) => setDayOfMonth(event.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Reference #
            </label>
            <input
              value={referenceNumber}
              onChange={(event) => setReferenceNumber(event.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Memo / remarks
            </label>
            <input
              value={memo}
              onChange={(event) => setMemo(event.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-5">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-slate-600">Account</th>
              <th className="text-left px-3 py-2 font-medium text-slate-600">Property</th>
              <th className="text-left px-3 py-2 font-medium text-slate-600">Description</th>
              <th className="text-right px-3 py-2 font-medium text-slate-600">Debit</th>
              <th className="text-right px-3 py-2 font-medium text-slate-600">Credit</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lines.map((row) => (
              <tr key={row.key} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  <select
                    value={row.gl_account_id}
                    onChange={(event) =>
                      updateRow(row.key, {
                        gl_account_id: event.target.value
                          ? Number(event.target.value)
                          : "",
                      })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 bg-white"
                  >
                    <option value="">Select account…</option>
                    {accounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.gl_number} {account.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <select
                    value={row.property_id}
                    onChange={(event) =>
                      updateRow(row.key, {
                        property_id: event.target.value
                          ? Number(event.target.value)
                          : "",
                      })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 bg-white"
                  >
                    <option value="">(none)</option>
                    {properties.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <input
                    value={row.description}
                    onChange={(event) =>
                      updateRow(row.key, { description: event.target.value })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={row.debit}
                    onChange={(event) =>
                      updateRow(row.key, {
                        debit: event.target.value,
                        credit: "",
                      })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-right"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={row.credit}
                    onChange={(event) =>
                      updateRow(row.key, {
                        credit: event.target.value,
                        debit: "",
                      })
                    }
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-right"
                  />
                </td>
                <td className="px-2 py-2">
                  <button
                    type="button"
                    onClick={() => removeRow(row.key)}
                    disabled={lines.length <= 2}
                    className="text-xs text-slate-400 hover:text-red-600 disabled:opacity-30"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-slate-50 border-t border-slate-200">
            <tr>
              <td colSpan={3} className="px-3 py-2">
                <button type="button" onClick={addRow} className="text-sm text-blue-600 hover:underline">
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
              <td colSpan={5} className="px-3 pb-3 text-right text-xs">
                <span className={balanced ? "text-green-600" : "text-red-600"}>
                  {balanced
                    ? "Balanced"
                    : `Off by ${formatMoney(Math.abs(totalDebit - totalCredit).toFixed(2))}`}
                </span>
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
          className="px-4 py-2 rounded-md border border-slate-300 text-sm font-medium"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => void submit()}
          disabled={saving || !balanced}
          className="px-4 py-2 rounded-md bg-slate-900 text-white text-sm font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Recurring Entry"}
        </button>
      </div>
    </div>
  );
}
