// ============================================================
// New Bill page
// ------------------------------------------------------------
// Route: /dashboard/accounting/bills/new
//
// Enter a bill (money going OUT). Posts to the GL as:
//   DR Expense line(s)  /  CR Accounts Payable
//
// Multi-line. Pick a payee, bill date, due date, then add
// expense lines. Total must equal sum of line amounts.
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createBill, BillCreateIn, BillLineIn } from "@/lib/bills";
import { apiGet } from "@/lib/api";
import { listGLAccounts, GLAccount } from "@/lib/glAccounts";

type Property = { id: number; name: string };

type LineRow = {
  key: string;
  gl_account_id: number;
  gl_account_number: string;
  gl_account_name: string;
  description: string;
  amount: number;
};

let rowCounter = 0;

export default function NewBillPage() {
  const router = useRouter();

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Reference data
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);

  // Form fields
  const [payeeName, setPayeeName] = useState("");
  const [billDate, setBillDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [dueDate, setDueDate] = useState<string>("");
  const [reference, setReference] = useState("");
  const [propertyId, setPropertyId] = useState<number | "">("");
  const [remarks, setRemarks] = useState("");
  const [lines, setLines] = useState<LineRow[]>([]);

  // Load reference data
  useEffect(() => {
    (async () => {
      try {
        const accts = await listGLAccounts(false);
        const flat: GLAccount[] = [];
        for (const g of accts.groups) flat.push(...g.accounts);
        setAccounts(flat);

        // Seed one row defaulting to first expense account (6xxx)
        const firstExpense =
          flat.find((a) => a.is_active && a.account_type === "EXPENSE") ??
          null;
        if (firstExpense) {
          rowCounter += 1;
          setLines([
            {
              key: `row-${Date.now()}-${rowCounter}`,
              gl_account_id: firstExpense.id,
              gl_account_number: firstExpense.gl_number,
              gl_account_name: firstExpense.name,
              description: "",
              amount: 0,
            },
          ]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load accounts");
      }

      try {
        const propsRaw = (await apiGet("/properties")) as unknown;
        const props: Property[] = Array.isArray(propsRaw)
          ? (propsRaw as Property[])
          : (((propsRaw as { items?: Property[] })?.items ?? []) as Property[]);
        setProperties(props);
      } catch {
        setProperties([]);
      }
    })();
  }, []);

  // Which accounts can be selected on a bill line?
  // Default: expense accounts. Also allow asset accounts
  // (e.g. paying for a building repair that capitalizes).
  const expenseAccounts = useMemo(
    () =>
      accounts.filter(
        (a) =>
          a.is_active &&
          (a.account_type === "EXPENSE" ||
            a.account_type === "ASSET")
      ),
    [accounts]
  );

  const total = lines.reduce((sum, r) => sum + Number(r.amount || 0), 0);

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
    const defaultAcct = expenseAccounts[0];
    setLines((prev) => [
      ...prev,
      {
        key: `row-${Date.now()}-${rowCounter}`,
        gl_account_id: defaultAcct?.id ?? 0,
        gl_account_number: defaultAcct?.gl_number ?? "",
        gl_account_name: defaultAcct?.name ?? "",
        description: "",
        amount: 0,
      },
    ]);
  }

  function accountLabel(a: GLAccount): string {
    return `${a.gl_number} ${a.name}`;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!payeeName.trim()) {
      setError("Payee name is required.");
      return;
    }
    const valid = lines.filter((r) => Number(r.amount) > 0);
    if (valid.length === 0) {
      setError("Add at least one line with an amount greater than zero.");
      return;
    }

    const payload: BillCreateIn = {
      payee_name: payeeName.trim(),
      bill_date: billDate,
      due_date: dueDate || null,
      reference_number: reference || null,
      property_id: propertyId ? Number(propertyId) : null,
      remarks: remarks || null,
      lines: valid.map<BillLineIn>((r) => ({
        gl_account_id: r.gl_account_id,
        description: r.description || null,
        amount: r.amount,
      })),
    };

    setSubmitting(true);
    try {
      const created = await createBill(payload);
      router.push(`/dashboard/accounting/bills`);
      void created;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create bill");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <Link
          href="/dashboard/accounting/bills"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Bills
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">Enter Bill</h1>
      </div>

      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Common fields */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="block text-xs text-slate-500 mb-1">
              Payee *
            </label>
            <input
              type="text"
              required
              value={payeeName}
              onChange={(e) => setPayeeName(e.target.value)}
              placeholder="Vendor or company name"
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Bill date *
            </label>
            <input
              type="date"
              required
              value={billDate}
              onChange={(e) => setBillDate(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Due date
            </label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
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
              placeholder="Vendor invoice #"
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Property</label>
            <select
              value={propertyId}
              onChange={(e) =>
                setPropertyId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            >
              <option value="">— None —</option>
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Remarks</label>
            <textarea
              rows={2}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Lines */}
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="text-sm font-semibold text-slate-700 mb-2">
            Expense Lines ({lines.length})
          </div>

          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  GL Account
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Description
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-32">
                  Amount
                </th>
                <th className="w-16"></th>
              </tr>
            </thead>
            <tbody>
              {lines.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-3 py-6 text-center text-slate-500 text-xs"
                  >
                    No lines yet. Click “+ Add line”.
                  </td>
                </tr>
              )}
              {lines.map((row) => (
                <tr key={row.key} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <select
                      value={row.gl_account_id}
                      onChange={(e) => {
                        const id = Number(e.target.value);
                        const acct = accounts.find((a) => a.id === id);
                        updateRow(row.key, {
                          gl_account_id: id,
                          gl_account_number: acct?.gl_number ?? "",
                          gl_account_name: acct?.name ?? "",
                        });
                      }}
                      className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                    >
                      <option value={0}>— Select —</option>
                      {expenseAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {accountLabel(a)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.description}
                      onChange={(e) =>
                        updateRow(row.key, { description: e.target.value })
                      }
                      placeholder="e.g. Fix kitchen sink"
                      className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.amount || ""}
                      onChange={(e) =>
                        updateRow(row.key, {
                          amount: Number(e.target.value) || 0,
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

              {/* Add-line row, right-aligned */}
              <tr className="border-t border-slate-100">
                <td colSpan={4} className="px-3 py-2 text-right">
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
            {lines.length > 0 && (
              <tfoot>
                <tr className="border-t border-slate-200 bg-slate-50">
                  <td
                    colSpan={2}
                    className="px-3 py-2 text-right font-medium text-slate-700"
                  >
                    Total
                  </td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">
                    {total.toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="text-sm px-5 py-2.5 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? "Posting…" : "Post Bill"}
          </button>
          <Link
            href="/dashboard/accounting/bills"
            className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}