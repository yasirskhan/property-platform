// ============================================================
// ImprovementsTab.tsx
// ------------------------------------------------------------
// Property detail tab: improvement / renovation history.
// AppFolio-parity field: warranty_expires.
//
// Uses formatMoney() from lib/money.ts so the org's currency
// setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import {
  listImprovements,
  createImprovement,
  updateImprovement,
  deleteImprovement,
  PropertyImprovement,
  PropertyImprovementCreateIn,
  PropertyImprovementUpdateIn,
} from "@/lib/propertyImprovements";
import { formatMoney } from "@/lib/money";

const CATEGORY_OPTIONS = [
  "Kitchen",
  "Bath",
  "Roof",
  "HVAC",
  "Flooring",
  "Electrical",
  "Plumbing",
  "Exterior",
  "Other",
];

type EditState = {
  improvement_date: string;
  description: string;
  cost: string;
  contractor: string;
  category: string;
  warranty_expires: string;
  notes: string;
};

const emptyEdit: EditState = {
  improvement_date: new Date().toISOString().slice(0, 10),
  description: "",
  cost: "",
  contractor: "",
  category: "",
  warranty_expires: "",
  notes: "",
};

export default function ImprovementsTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [items, setItems] = useState<PropertyImprovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const [showAddForm, setShowAddForm] = useState(false);
  const [add, setAdd] = useState<EditState>({ ...emptyEdit });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [edit, setEdit] = useState<EditState>({ ...emptyEdit });

  const [confirmingDelete, setConfirmingDelete] =
    useState<PropertyImprovement | null>(null);
  const [deleteReason, setDeleteReason] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listImprovements(propertyId, false);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  function toPayload(
    s: EditState
  ): Omit<PropertyImprovementCreateIn, "property_id"> &
    PropertyImprovementUpdateIn {
    return {
      improvement_date: s.improvement_date,
      description: s.description.trim(),
      cost: s.cost ? Number(s.cost) : null,
      contractor: s.contractor || null,
      category: s.category || null,
      warranty_expires: s.warranty_expires || null,
      notes: s.notes || null,
    };
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!add.description.trim()) return;
    setWorking(true);
    setError("");
    try {
      await createImprovement(propertyId, toPayload(add));
      setAdd({ ...emptyEdit });
      setShowAddForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setWorking(false);
    }
  }

  function startEdit(i: PropertyImprovement) {
    setEditingId(i.id);
    setEdit({
      improvement_date: i.improvement_date,
      description: i.description,
      cost: i.cost || "",
      contractor: i.contractor || "",
      category: i.category || "",
      warranty_expires: i.warranty_expires || "",
      notes: i.notes || "",
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setEdit({ ...emptyEdit });
  }

  async function saveEdit(id: number) {
    setWorking(true);
    setError("");
    try {
      await updateImprovement(propertyId, id, toPayload(edit));
      cancelEdit();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setWorking(false);
    }
  }

  function askDelete(i: PropertyImprovement) {
    setDeleteReason("");
    setConfirmingDelete(i);
  }

  async function reallyDelete(i: PropertyImprovement) {
    setWorking(true);
    setError("");
    try {
      await deleteImprovement(propertyId, i.id, deleteReason);
      setConfirmingDelete(null);
      setDeleteReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setWorking(false);
    }
  }

  function money(v: string | null): string {
    if (!v) return "—";
    return formatMoney(v);
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div>
      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {canEdit && !showAddForm && (
        <div className="mb-4 text-right">
          <button
            onClick={() => setShowAddForm(true)}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Improvement
          </button>
        </div>
      )}

      {canEdit && showAddForm && (
        <form
          onSubmit={handleAdd}
          className="bg-white border border-slate-200 rounded-xl p-5 mb-6"
        >
          <div className="text-sm font-semibold text-slate-700 mb-3">
            New Improvement
          </div>
          <ImprovementFields value={add} onChange={setAdd} />
          <div className="flex items-center gap-3 pt-4">
            <button
              type="submit"
              disabled={working || !add.description.trim()}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              {working ? "Adding…" : "Add"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowAddForm(false);
                setAdd({ ...emptyEdit });
              }}
              disabled={working}
              className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {items.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-500 text-sm">
          No improvements logged yet.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Date
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Description
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Category
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-44">
                  Contractor
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-24">
                  Cost
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Warranty
                </th>
                {canEdit && <th className="w-28"></th>}
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-t border-slate-100">
                  {editingId === i.id ? (
                    <td colSpan={canEdit ? 7 : 6} className="px-3 py-3">
                      <ImprovementFields value={edit} onChange={setEdit} />
                      <div className="flex items-center gap-3 pt-3">
                        <button
                          onClick={() => saveEdit(i.id)}
                          disabled={working}
                          className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
                        >
                          {working ? "Saving…" : "Save"}
                        </button>
                        <button
                          onClick={cancelEdit}
                          disabled={working}
                          className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
                        >
                          Cancel
                        </button>
                      </div>
                    </td>
                  ) : (
                    <>
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {i.improvement_date}
                      </td>
                      <td className="px-3 py-2 text-slate-800">
                        {i.description}
                        {i.notes && (
                          <div className="text-xs text-slate-500 mt-0.5">
                            {i.notes}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {i.category || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {i.contractor || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-700 text-xs text-right font-mono">
                        {money(i.cost)}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {i.warranty_expires || "—"}
                      </td>
                      {canEdit && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button
                            onClick={() => startEdit(i)}
                            className="text-blue-600 hover:text-blue-800 text-xs"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => askDelete(i)}
                            className="text-red-600 hover:text-red-800 text-xs ml-3"
                          >
                            Remove
                          </button>
                        </td>
                      )}
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirmingDelete && (
        <>
          <div
            className="fixed inset-0 bg-black/40 z-40"
            onClick={() => !working && setConfirmingDelete(null)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <div className="w-full max-w-md bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
              <div className="px-6 py-4 border-b border-slate-200">
                <div className="font-semibold text-slate-900 text-lg">
                  Remove improvement?
                </div>
              </div>
              <div className="px-6 py-5 text-sm text-slate-700 space-y-3">
                Remove{" "}
                <strong>{confirmingDelete.description.slice(0, 60)}</strong>{" "}
                from this property?
                <div>
    <label className="block text-xs font-medium text-slate-600 mb-1">Reason for removal *</label>
    <textarea
      value={deleteReason}
      onChange={(e) => setDeleteReason(e.target.value)}
      rows={3}
      maxLength={1000}
      placeholder="Explain why this item is being removed"
      className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
    />
  </div>
</div>
              <div className="border-t border-slate-200 p-4 flex items-center justify-end gap-3">
                <button
                  onClick={() => setConfirmingDelete(null)}
                  disabled={working}
                  className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
                >
                  Cancel
                </button>
                <button
                  onClick={() => reallyDelete(confirmingDelete)}
                  disabled={working || !deleteReason.trim()}
                  className="text-sm px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {working ? "Removing…" : "Remove"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ImprovementFields({
  value,
  onChange,
}: {
  value: EditState;
  onChange: (v: EditState) => void;
}) {
  function set<K extends keyof EditState>(key: K, v: EditState[K]) {
    onChange({ ...value, [key]: v });
  }

  return (
    <div className="grid grid-cols-12 gap-3">
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">Date *</label>
        <input
          type="date"
          value={value.improvement_date}
          onChange={(e) => set("improvement_date", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-6">
        <label className="block text-xs text-slate-500 mb-1">
          Description *
        </label>
        <input
          type="text"
          value={value.description}
          onChange={(e) => set("description", e.target.value)}
          placeholder="e.g. New kitchen countertops"
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">Category</label>
        <select
          value={value.category}
          onChange={(e) => set("category", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        >
          <option value="">— None —</option>
          {CATEGORY_OPTIONS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <div className="col-span-4">
        <label className="block text-xs text-slate-500 mb-1">
          Contractor
        </label>
        <input
          type="text"
          value={value.contractor}
          onChange={(e) => set("contractor", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">Cost</label>
        <input
          type="number"
          step="0.01"
          min="0"
          value={value.cost}
          onChange={(e) => set("cost", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm font-mono"
        />
      </div>
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">
          Warranty expires
        </label>
        <input
          type="date"
          value={value.warranty_expires}
          onChange={(e) => set("warranty_expires", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-12">
        <label className="block text-xs text-slate-500 mb-1">Notes</label>
        <input
          type="text"
          value={value.notes}
          onChange={(e) => set("notes", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
    </div>
  );
}