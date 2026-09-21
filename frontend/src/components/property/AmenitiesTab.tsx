// ============================================================
// AmenitiesTab.tsx
// ------------------------------------------------------------
// Property detail tab: amenities list with inline add/edit.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import {
  listAmenities,
  createAmenity,
  updateAmenity,
  deleteAmenity,
  PropertyAmenity,
} from "@/lib/propertyAmenities";

const CATEGORY_OPTIONS = [
  "Building",
  "Unit",
  "Outdoor",
  "Community",
  "Other",
];

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

  // Inline add form
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [newNotes, setNewNotes] = useState("");

  // Inline edit
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editNotes, setEditNotes] = useState("");

  // Confirm-delete modal state
  const [confirmingDelete, setConfirmingDelete] =
    useState<PropertyAmenity | null>(null);

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

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setWorking(true);
    setError("");
    try {
      await createAmenity(propertyId, {
        name: newName.trim(),
        category: newCategory || null,
        notes: newNotes || null,
      });
      setNewName("");
      setNewCategory("");
      setNewNotes("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setWorking(false);
    }
  }

  function startEdit(a: PropertyAmenity) {
    setEditingId(a.id);
    setEditName(a.name);
    setEditCategory(a.category || "");
    setEditNotes(a.notes || "");
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function handleSaveEdit(id: number) {
    setWorking(true);
    setError("");
    try {
      await updateAmenity(propertyId, id, {
        name: editName.trim(),
        category: editCategory || null,
        notes: editNotes || null,
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setWorking(false);
    }
  }

  function handleDelete(a: PropertyAmenity) {
    setConfirmingDelete(a);
  }

  async function reallyDelete(a: PropertyAmenity) {
    setWorking(true);
    setError("");
    try {
      await deleteAmenity(propertyId, a.id);
      setConfirmingDelete(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="max-w-3xl">
      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Add form */}
      {canEdit && (
        <form
          onSubmit={handleAdd}
          className="bg-white border border-slate-200 rounded-xl p-4 mb-6 grid grid-cols-12 gap-3 items-end"
        >
          <div className="col-span-4">
            <label className="block text-xs text-slate-500 mb-1">
              Amenity *
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Pool"
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="col-span-3">
            <label className="block text-xs text-slate-500 mb-1">
              Category
            </label>
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
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
            <label className="block text-xs text-slate-500 mb-1">Notes</label>
            <input
              type="text"
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="col-span-2">
            <button
              type="submit"
              disabled={working || !newName.trim()}
              className="w-full text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </form>
      )}

      {/* List */}
      {items.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-500 text-sm">
          No amenities yet.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-700">
                  Amenity
                </th>
                <th className="text-left px-4 py-2 font-medium text-slate-700 w-32">
                  Category
                </th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">
                  Notes
                </th>
                {canEdit && <th className="w-32"></th>}
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  {editingId === a.id ? (
                    <>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <select
                          value={editCategory}
                          onChange={(e) => setEditCategory(e.target.value)}
                          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                        >
                          <option value="">— None —</option>
                          {CATEGORY_OPTIONS.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                        />
                      </td>
                      <td className="px-4 py-2 text-right whitespace-nowrap">
                        <button
                          onClick={() => handleSaveEdit(a.id)}
                          disabled={working}
                          className="text-blue-600 hover:text-blue-800 text-xs disabled:opacity-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEdit}
                          disabled={working}
                          className="text-slate-500 hover:text-slate-700 text-xs ml-3"
                        >
                          Cancel
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-2 text-slate-800">{a.name}</td>
                      <td className="px-4 py-2 text-slate-500 text-xs">
                        {a.category || "—"}
                      </td>
                      <td className="px-4 py-2 text-slate-500 text-xs">
                        {a.notes || "—"}
                      </td>
                      {canEdit && (
                        <td className="px-4 py-2 text-right whitespace-nowrap">
                          <button
                            onClick={() => startEdit(a)}
                            className="text-blue-600 hover:text-blue-800 text-xs"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDelete(a)}
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

      {/* Confirm-delete modal */}
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
              <div className="px-6 py-5 text-sm text-slate-700">
                Are you sure you want to remove{" "}
                <strong>{confirmingDelete.name}</strong> from this property?
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
                  disabled={working}
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