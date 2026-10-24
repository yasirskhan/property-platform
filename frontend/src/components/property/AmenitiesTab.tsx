// ============================================================
// AmenitiesTab.tsx
// Amenities list with inline add/edit + styled confirm modal.
// Includes AppFolio-parity fields: fee_amount,
// availability_status.
//
// Uses formatMoney() from lib/money.ts so the org's currency
// setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import {
  listAmenities,
  createAmenity,
  updateAmenity,
  deleteAmenity,
  PropertyAmenity,
  PropertyAmenityCreateIn,
  PropertyAmenityUpdateIn,
} from "@/lib/propertyAmenities";
import { formatMoney } from "@/lib/money";

const CATEGORY_OPTIONS = [
  "Building",
  "Unit",
  "Outdoor",
  "Community",
  "Other",
];

type AvailabilityValue = "INCLUDED" | "EXTRA_FEE" | "NOT_AVAILABLE";

const AVAILABILITY_OPTIONS: { value: AvailabilityValue; label: string }[] = [
  { value: "INCLUDED", label: "Included" },
  { value: "EXTRA_FEE", label: "Extra Fee" },
  { value: "NOT_AVAILABLE", label: "Not Available" },
];

type EditState = {
  name: string;
  category: string;
  notes: string;
  fee_amount: string;
  availability_status: "" | AvailabilityValue;
};

const emptyEdit: EditState = {
  name: "",
  category: "",
  notes: "",
  fee_amount: "",
  availability_status: "",
};

export default function AmenitiesTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [items, setItems] = useState<PropertyAmenity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const [newRow, setNewRow] = useState<EditState>({ ...emptyEdit });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [edit, setEdit] = useState<EditState>({ ...emptyEdit });

  const [confirmingDelete, setConfirmingDelete] =
    useState<PropertyAmenity | null>(null);
  const [deleteReason, setDeleteReason] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listAmenities(propertyId, false);
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
  ): Omit<PropertyAmenityCreateIn, "property_id"> & PropertyAmenityUpdateIn {
    return {
      name: s.name.trim(),
      category: s.category || null,
      notes: s.notes || null,
      fee_amount: s.fee_amount ? Number(s.fee_amount) : null,
      availability_status: s.availability_status || null,
    };
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newRow.name.trim()) return;
    setWorking(true);
    setError("");
    try {
      await createAmenity(propertyId, toPayload(newRow));
      setNewRow({ ...emptyEdit });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setWorking(false);
    }
  }

  function startEdit(a: PropertyAmenity) {
    setEditingId(a.id);
    setEdit({
      name: a.name,
      category: a.category || "",
      notes: a.notes || "",
      fee_amount: a.fee_amount || "",
      availability_status: (a.availability_status ||
        "") as EditState["availability_status"],
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
      await updateAmenity(propertyId, id, toPayload(edit));
      cancelEdit();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setWorking(false);
    }
  }

  function askDelete(a: PropertyAmenity) {
    setDeleteReason("");
    setConfirmingDelete(a);
  }

  async function reallyDelete(a: PropertyAmenity) {
    setWorking(true);
    setError("");
    try {
      await deleteAmenity(propertyId, a.id, deleteReason);
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

  function availabilityLabel(v: string | null): string {
    if (!v) return "—";
    const found = AVAILABILITY_OPTIONS.find((o) => o.value === v);
    return found ? found.label : v;
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="max-w-4xl">
      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {canEdit && (
        <form
          onSubmit={handleAdd}
          className="bg-white border border-slate-200 rounded-xl p-4 mb-6"
        >
          <div className="text-sm font-semibold text-slate-700 mb-3">
            New amenity
          </div>
          <AmenityFields value={newRow} onChange={setNewRow} />
          <div className="flex items-center gap-3 pt-3">
            <button
              type="submit"
              disabled={working || !newRow.name.trim()}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              {working ? "Adding…" : "Add"}
            </button>
          </div>
        </form>
      )}

      {items.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-500 text-sm">
          No amenities yet.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Amenity
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Category
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-28">
                  Availability
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-24">
                  Fee
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Notes
                </th>
                {canEdit && <th className="w-28"></th>}
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  {editingId === a.id ? (
                    <td colSpan={canEdit ? 6 : 5} className="px-3 py-3">
                      <AmenityFields value={edit} onChange={setEdit} />
                      <div className="flex items-center gap-3 pt-3">
                        <button
                          onClick={() => saveEdit(a.id)}
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
                      <td className="px-3 py-2 text-slate-800">{a.name}</td>
                      <td className="px-3 py-2 text-slate-500 text-xs">
                        {a.category || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-500 text-xs">
                        {availabilityLabel(a.availability_status)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs text-slate-700">
                        {money(a.fee_amount)}
                      </td>
                      <td className="px-3 py-2 text-slate-500 text-xs">
                        {a.notes || "—"}
                      </td>
                      {canEdit && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button
                            onClick={() => startEdit(a)}
                            className="text-blue-600 hover:text-blue-800 text-xs"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => askDelete(a)}
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
                  Remove amenity?
                </div>
              </div>
              <div className="px-6 py-5 text-sm text-slate-700 space-y-3">
                Remove <strong>{confirmingDelete.name}</strong> from this
                property?
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

function AmenityFields({
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
      <div className="col-span-4">
        <label className="block text-xs text-slate-500 mb-1">Name *</label>
        <input
          type="text"
          value={value.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="e.g. Pool"
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-2">
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
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">
          Availability
        </label>
        <select
          value={value.availability_status}
          onChange={(e) =>
            set(
              "availability_status",
              e.target.value as EditState["availability_status"]
            )
          }
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        >
          <option value="">— None —</option>
          {AVAILABILITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">
          Fee amount
        </label>
        <input
          type="number"
          step="0.01"
          min="0"
          value={value.fee_amount}
          onChange={(e) => set("fee_amount", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm font-mono"
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