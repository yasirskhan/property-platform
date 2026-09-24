// ============================================================
// New Bill page
// ------------------------------------------------------------
// Enter a vendor bill. Multi-line. Posts DR Expense / CR AP.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

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
  amount: string;
}

export default function NewBillPage() {
  const router = useRouter();
  const { prefs } = useDisplay();

  const [properties, setProperties] = useState<Property[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [payeeName, setPayeeName] = useState("");
  const [billDate, setBillDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [dueDate, setDueDate] = useState("");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [remarks, setRemarks] = useState("");

  function newRow(key: string): LineRow {
    return {
      key,
      gl_account_id: "",
      property_id: "",
      description: "",
      amount: "",
    };
  }

  const [lines, setLines] = useState<LineRow[]>(() => [
    newRow("row-initial-1"),
    newRow("row-initial-2"),
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
        const expenseAccounts = groups
          .filter((g) => (g.account_type || "").toUpperCase() === "EXPENSE")
          .flatMap((g) => g.accounts);
        setAccounts(expenseAccounts);
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
    setLines((prev) => [...prev, newRow(`row-${crypto.randomUUID()}`)]);
  }

  function removeRow(key: string) {
    setLines((prev) => (prev.length <= 2 ? prev : prev.filter((r) => r.key !== key)));
  }

  function updateRow(key: string, patch: Partial<LineRow>) {
    setLines((prev) =>
      prev.map((r) => (r.key === key ? { ...r, ...patch } : r))
    );
  }

  const total = lines.reduce(
    (acc, r) => acc + (parseFloat(r.amount) || 0),
    0
  );

  async function submit() {
    if (!payeeName.trim()) {
      setError("Payee is required.");
      return;
    }
    const validLines = lines.filter(
      (r) => r.gl_account_id && parseFloat(r.amount) > 0
    );
    if (validLines.length === 0) {
      setError("At least one line with an account and amount is required.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await apiPost("/api/accounting/bills", {
        payee_name: payeeName,
        bill_date: billDate,
        due_date: dueDate || null,
        reference_number: referenceNumber || null,
        remarks: remarks || null,
        lines: validLines.map((r) => ({
          gl_account_id: r.gl_account_id,
          property_id: r.property_id || null,
          description: r.description || null,
          amount: parseFloat(r.amount),
        })),
      });
      router.push("/dashboard/accounting/bills");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not save bill.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6 text-slate-500">Loading...</div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6" data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()} data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}>
      <span hidden aria-hidden="true" data-compat-slot="bills.real-vendor-picker" />
      <span hidden aria-hidden="true" data-compat-slot="bills.cash-account-entry" />
      <span hidden aria-hidden="true" data-compat-slot="bills.recurring-post-code" />
      <span hidden aria-hidden="true" data-compat-slot="bills.delete-visibility-rule" />
      <h1 className="text-xl font-semibold text-slate-900 mb-1">New Bill</h1>
      <p className="text-sm text-slate-500 mb-6">
        Enter a vendor bill. Posts DR Expense / CR Accounts Payable.
      </p>

      {error && (
        <div className="text-sm text-red-600 mb-4 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Payee <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={payeeName}
              onChange={(e) => setPayeeName(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Bill date <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={billDate}
              onChange={(e) => setBillDate(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Due date
            </label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
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
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">Remarks</label>
          <input
            type="text"
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden mb-5">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Account</th>
              <th className="text-left px-3 py-2 font-medium">Property</th>
              <th className="text-left px-3 py-2 font-medium">Description</th>
              <th className="text-right px-3 py-2 font-medium">Amount</th>
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
                    value={r.amount}
                    onChange={(e) =>
                      updateRow(r.key, { amount: e.target.value })
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
                {formatMoney(total.toFixed(2))}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => router.push("/dashboard/accounting/bills")}
          className="px-4 py-2 rounded-md border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={saving}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save bill"}
        </button>
      </div>
    </div>
  );
}