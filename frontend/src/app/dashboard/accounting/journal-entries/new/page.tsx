// ============================================================
// New Journal Entry page
// ------------------------------------------------------------
// Route: /dashboard/accounting/journal-entries/new
//
// Manual journal entry form. Manager picks a date, an optional
// reference/memo, and builds a list of debit/credit lines.
// Live balance check tells them when the JE balances.
//
// On submit, POSTs to /api/accounting/journal-entries.
// On success, redirects to the detail view.
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createJournalEntry, JournalEntryLineIn } from "@/lib/journalEntries";
import { listGLAccounts, GLAccount } from "@/lib/glAccounts";

type Property = { id: number; name: string };

type LineRow = {
  key: string;
  gl_account_id: number;
  property_id: number | "";
  description: string;
  debit: number;
  credit: number;
};

let rowCounter = 0;

export default function NewJournalEntryPage() {
  const router = useRouter();

  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);

  const [entryDate, setEntryDate] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [reference, setReference] = useState("");
  const [memo, setMemo] = useState("");

  const [lines, setLines] = useState<LineRow[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Load reference data + add two blank rows on mount
  useEffect(() => {
    (async () => {
      try {
        const accts = await listGLAccounts(false);
        const flat: GLAccount[] = [];
        for (const g of accts.groups) flat.push(...g.accounts);
        setAccounts(flat);

        // Start with 2 blank rows
        rowCounter += 2;
        setLines([
          {
            key: `row-${Date.now()}-1`,
            gl_account_id: 0,
            property_id: "",
            description: "",
            debit: 0,
            credit: 0,
          },
          {
            key: `row-${Date.now()}-2`,
            gl_account_id: 0,
            property_id: "",
            description: "",
            debit: 0,
            credit: 0,
          },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load accounts");
      }

      try {
        const propsRaw = (await (
          await import("@/lib/api")
        ).apiGet("/properties")) as unknown;
        const props: Property[] = Array.isArray(propsRaw)
          ? (propsRaw as Property[])
          : (((propsRaw as { items?: Property[] })?.items ?? []) as Property[]);
        setProperties(props);
      } catch {
        setProperties([]);
      }
    })();
  }, []);

  const sortedAccounts = useMemo(
    () =>
      [...accounts].sort((a, b) =>
        a.gl_number.localeCompare(b.gl_number)
      ),
    [accounts]
  );

  const totalDebit = lines.reduce(
    (s, r) => s + Number(r.debit || 0),
    0
  );
  const totalCredit = lines.reduce(
    (s, r) => s + Number(r.credit || 0),
    0
  );
  const diff = Math.abs(totalDebit - totalCredit);
  const isBalanced =
    totalDebit > 0 && diff <= 0.01;

  function updateRow(key: string, patch: Partial<LineRow>) {
    setLines((prev) =>
      prev.map((r) => (r.key === key ? { ...r, ...patch } : r))
    );
  }

  function removeRow(key: string) {
    setLines((prev) => prev.filter((r) => r.key !== key));
  }

  function addRow() {
    rowCounter += 1;
    setLines((prev) => [
      ...prev,
      {
        key: `row-${Date.now()}-${rowCounter}`,
        gl_account_id: 0,
        property_id: "",
        description: "",
        debit: 0,
        credit: 0,
      },
    ]);
  }

  function accountLabel(a: GLAccount): string {
    return `${a.gl_number} ${a.name}`;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const valid = lines.filter(
      (l) =>
        l.gl_account_id > 0 &&
        (Number(l.debit) > 0 || Number(l.credit) > 0)
    );
    if (valid.length < 2) {
      setError("At least two complete lines are required.");
      return;
    }
    if (!isBalanced) {
      setError(
        `Journal entry does not balance (debits $${totalDebit.toFixed(
          2
        )} vs credits $${totalCredit.toFixed(2)}).`
      );
      return;
    }

    // Each line must have exactly one of debit/credit
    for (const l of valid) {
      const d = Number(l.debit) || 0;
      const c = Number(l.credit) || 0;
      if (d > 0 && c > 0) {
        setError("Each line can have debit OR credit, not both.");
        return;
      }
    }

    const payload = {
      transaction_date: entryDate,
      reference_number: reference || null,
      memo: memo || null,
      lines: valid.map<JournalEntryLineIn>((r) => ({
        gl_account_id: r.gl_account_id,
        property_id: r.property_id ? Number(r.property_id) : null,
        description: r.description || null,
        debit: Number(r.debit) || 0,
        credit: Number(r.credit) || 0,
      })),
    };

    setSubmitting(true);
    try {
      const created = await createJournalEntry(payload);
      router.push(
        `/dashboard/accounting/journal-entries/${created.id}`
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to post journal entry"
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <Link
          href="/dashboard/accounting/journal-entries"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Journal Entries
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">
          New Journal Entry
        </h1>
      </div>

      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Header fields */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Date *
            </label>
            <input
              type="date"
              required
              value={entryDate}
              onChange={(e) => setEntryDate(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Reference #
            </label>
            <input
              type="text"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Memo</label>
            <input
              type="text"
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Lines */}
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="text-sm font-semibold text-slate-700 mb-2">
            Lines ({lines.length})
          </div>

          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  GL Account
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-40">
                  Property
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Description
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-32">
                  Debit
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-32">
                  Credit
                </th>
                <th className="w-16"></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((row) => (
                <tr key={row.key} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <select
                      value={row.gl_account_id}
                      onChange={(e) =>
                        updateRow(row.key, {
                          gl_account_id: Number(e.target.value),
                        })
                      }
                      className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                    >
                      <option value={0}>— Select —</option>
                      {sortedAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {accountLabel(a)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <select
                      value={row.property_id}
                      onChange={(e) =>
                        updateRow(row.key, {
                          property_id: e.target.value
                            ? Number(e.target.value)
                            : "",
                        })
                      }
                      className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                    >
                      <option value="">— None —</option>
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
                      value={row.description}
                      onChange={(e) =>
                        updateRow(row.key, {
                          description: e.target.value,
                        })
                      }
                      className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.debit || ""}
                      onChange={(e) =>
                        updateRow(row.key, {
                          debit: Number(e.target.value) || 0,
                          credit: 0,
                        })
                      }
                      className="w-full border border-slate-300 rounded px-2 py-1 text-sm text-right font-mono"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.credit || ""}
                      onChange={(e) =>
                        updateRow(row.key, {
                          credit: Number(e.target.value) || 0,
                          debit: 0,
                        })
                      }
                      className="w-full border border-slate-300 rounded px-2 py-1 text-sm text-right font-mono"
                    />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => removeRow(row.key)}
                      className="text-red-600 hover:text-red-800 text-xs"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              <tr className="border-t border-slate-100">
                <td colSpan={6} className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={addRow}
                    className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded"
                  >
                    + Add line
                  </button>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr className="border-t border-slate-200 bg-slate-50">
                <td colSpan={3} className="px-3 py-2 text-right font-medium text-slate-700">
                  Totals
                </td>
                <td className="px-3 py-2 text-right font-mono font-semibold">
                  {totalDebit.toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
                <td className="px-3 py-2 text-right font-mono font-semibold">
                  {totalCredit.toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
                <td></td>
              </tr>
              <tr className="bg-slate-50">
                <td colSpan={6} className="px-3 py-2 text-right">
                  {isBalanced ? (
                    <span className="text-xs text-green-700">
                      ✓ Balanced
                    </span>
                  ) : (
                    <span className="text-xs text-red-600">
                      Not balanced — difference{" "}
                      {diff.toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </span>
                  )}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting || !isBalanced}
            className="text-sm px-5 py-2.5 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? "Posting…" : "Post Journal Entry"}
          </button>
          <Link
            href="/dashboard/accounting/journal-entries"
            className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}