// ============================================================
// ExpensesTab.tsx
// ------------------------------------------------------------
// Property detail tab: expenses (manual + auto-linked from
// insurance / mortgage / tax / utility / improvement).
//
// Uses formatMoney() from lib/money.ts so the org's currency
// setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { formatMoney } from "@/lib/money";
import { apiGet } from "@/lib/api";

type Expense = {
  id: number;
  property_id: number;
  category: string;
  amount: string;
  description: string;
  expense_date: string;
  source: string;
  source_id: number | null;
  notes: string | null;
  receipt_url: string | null;
  created_at: string;
};

type Summary = {
  total: number;
  by_category: Record<string, number>;
};

const CATEGORIES = [
  { value: "insurance", label: "Insurance" },
  { value: "mortgage", label: "Mortgage" },
  { value: "taxes", label: "Taxes" },
  { value: "utilities", label: "Utilities" },
  { value: "repairs", label: "Repairs" },
  { value: "maintenance", label: "Maintenance" },
  { value: "management", label: "Management" },
  { value: "hoa", label: "HOA" },
  { value: "legal", label: "Legal" },
  { value: "marketing", label: "Marketing" },
  { value: "supplies", label: "Supplies" },
  { value: "other", label: "Other" },
];

const SOURCE_LABELS: Record<string, string> = {
  manual: "Manual",
  insurance: "From insurance",
  mortgage: "From mortgage",
  tax: "From tax",
  utility: "From utility",
  improvement: "From improvement",
  other: "Other",
};

export default function ExpensesTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [filterCategory, setFilterCategory] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const url = filterCategory
        ? `/properties/${propertyId}/expenses?category=${filterCategory}`
        : `/properties/${propertyId}/expenses`;
      const [list, sum] = await Promise.all([
        apiGet(url).catch(() => []),
        apiGet(`/properties/${propertyId}/expenses/summary`).catch(() => null),
      ]);
      setExpenses(list);
      setSummary(sum);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId, filterCategory]);

  async function handleDelete(id: number) {
    if (!confirm("Delete this expense?")) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/properties/${propertyId}/expenses/${id}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Delete failed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <p className="text-slate-600">
            {expenses.length} {expenses.length === 1 ? "expense" : "expenses"}
          </p>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="text-sm px-3 py-1 border border-slate-300 rounded-lg"
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        {canEdit && (
          <button
            onClick={() => {
              setEditingId(null);
              setShowForm(true);
            }}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Expense
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {/* Summary */}
      {summary && summary.total > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 mb-6">
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-sm text-slate-600">Total (all time)</p>
            <p className="text-2xl font-bold text-slate-900">
              {formatMoney(summary.total)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.by_category).map(([cat, amt]) => (
              <span
                key={cat}
                className="text-xs px-2 py-1 bg-white border border-slate-200 rounded-full"
              >
                <span className="font-medium capitalize">
                  {cat.replace("_", " ")}
                </span>
                : {formatMoney(amt)}
              </span>
            ))}
          </div>
        </div>
      )}

      {showForm && (
        <ExpenseForm
          propertyId={propertyId}
          expenseId={editingId}
          onCancel={() => {
            setShowForm(false);
            setEditingId(null);
          }}
          onSaved={() => {
            setShowForm(false);
            setEditingId(null);
            load();
          }}
        />
      )}

      {expenses.length === 0 && !showForm ? (
        <p className="text-slate-500">No expenses recorded yet.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Date</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Category</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Description</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Source</th>
                <th className="text-right px-4 py-3 font-medium text-slate-500">Amount</th>
                {canEdit && <th className="px-4 py-3"></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {expenses.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-600">{e.expense_date}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-1 bg-slate-100 rounded-full capitalize">
                      {e.category.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-900">{e.description}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {SOURCE_LABELS[e.source] || e.source}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-slate-900 font-mono">
                    {formatMoney(e.amount)}
                  </td>
                  {canEdit && (
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {e.source === "manual" && (
                        <>
                          <button
                            onClick={() => {
                              setEditingId(e.id);
                              setShowForm(true);
                            }}
                            className="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-100 mr-1"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDelete(e.id)}
                            className="text-xs px-2 py-1 border border-red-200 text-red-700 rounded hover:bg-red-50"
                          >
                            ×
                          </button>
                        </>
                      )}
                      {e.source !== "manual" && (
                        <span className="text-xs text-slate-400 italic">
                          auto-linked
                        </span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// FORM
// ------------------------------------------------------------
function ExpenseForm({
  propertyId,
  expenseId,
  onCancel,
  onSaved,
}: {
  propertyId: number;
  expenseId: number | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [category, setCategory] = useState("other");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [expenseDate, setExpenseDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        category,
        amount: Number(amount),
        description,
        expense_date: expenseDate,
        notes: notes || null,
      };

      const token = localStorage.getItem("token");
      const url = expenseId
        ? `http://127.0.0.1:8000/properties/${propertyId}/expenses/${expenseId}`
        : `http://127.0.0.1:8000/properties/${propertyId}/expenses`;
      const method = expenseId ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Save failed");
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-50 rounded-xl border border-slate-200 p-6 mb-4 space-y-4">
      <h4 className="font-semibold text-slate-900">
        {expenseId ? "Edit Expense" : "New Expense"}
      </h4>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Category</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="input">
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Amount</label>
          <input
            type="number"
            step="0.01"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="input"
          />
        </div>

        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
          <input
            type="text"
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What was this for?"
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Date</label>
          <input
            type="date"
            required
            value={expenseDate}
            onChange={(e) => setExpenseDate(e.target.value)}
            className="input"
          />
        </div>

        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="input"
          />
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : expenseId ? "Update" : "Add Expense"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-sm font-medium border border-slate-300 hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}