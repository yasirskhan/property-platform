// ============================================================
// AppliancesTab.tsx
// ------------------------------------------------------------
// Property detail tab: appliances list with add/edit inline.
// AppFolio-parity field: condition.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import {
  listAppliances,
  createAppliance,
  updateAppliance,
  deleteAppliance,
  PropertyAppliance,
  PropertyApplianceCondition,
  PropertyApplianceCreateIn,
  PropertyApplianceUpdateIn,
} from "@/lib/propertyAppliances";
import { formatMoney } from "@/lib/money";

const COMMON_APPLIANCES = [
  "Refrigerator",
  "Washer",
  "Dryer",
  "Dishwasher",
  "Microwave",
  "Range / Oven",
  "Water Heater",
  "HVAC",
  "Garbage Disposal",
  "Other",
];

const CONDITION_OPTIONS: {
  value: PropertyApplianceCondition;
  label: string;
}[] = [
  { value: "NEW", label: "New" },
  { value: "GOOD", label: "Good" },
  { value: "FAIR", label: "Fair" },
  { value: "NEEDS_REPAIR", label: "Needs Repair" },
];

type EditState = {
  name: string;
  brand: string;
  model_number: string;
  serial_number: string;
  purchase_date: string;
  purchase_price: string;
  warranty_expires: string;
  condition: "" | PropertyApplianceCondition;
  notes: string;
};

const emptyEdit: EditState = {
  name: "",
  brand: "",
  model_number: "",
  serial_number: "",
  purchase_date: "",
  purchase_price: "",
  warranty_expires: "",
  condition: "",
  notes: "",
};

export default function AppliancesTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [items, setItems] = useState<PropertyAppliance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const [showAddForm, setShowAddForm] = useState(false);
  const [add, setAdd] = useState<EditState>({ ...emptyEdit });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [edit, setEdit] = useState<EditState>({ ...emptyEdit });

  const [confirmingDelete, setConfirmingDelete] =
    useState<PropertyAppliance | null>(null);
  const [deleteReason, setDeleteReason] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listAppliances(propertyId, false);
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
  ): Omit<PropertyApplianceCreateIn, "property_id"> &
    PropertyApplianceUpdateIn {
    return {
      name: s.name.trim(),
      brand: s.brand || null,
      model_number: s.model_number || null,
      serial_number: s.serial_number || null,
      purchase_date: s.purchase_date || null,
      purchase_price: s.purchase_price ? Number(s.purchase_price) : null,
      warranty_expires: s.warranty_expires || null,
      condition: s.condition || null,
      notes: s.notes || null,
    };
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!add.name.trim()) return;
    setWorking(true);
    setError("");
    try {
      await createAppliance(propertyId, toPayload(add));
      setAdd({ ...emptyEdit });
      setShowAddForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setWorking(false);
    }
  }

  function startEdit(a: PropertyAppliance) {
    setEditingId(a.id);
    setEdit({
      name: a.name,
      brand: a.brand || "",
      model_number: a.model_number || "",
      serial_number: a.serial_number || "",
      purchase_date: a.purchase_date || "",
      purchase_price: a.purchase_price || "",
      warranty_expires: a.warranty_expires || "",
      condition: (a.condition ||
        "") as EditState["condition"],
      notes: a.notes || "",
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
      await updateAppliance(propertyId, id, toPayload(edit));
      cancelEdit();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setWorking(false);
    }
  }

  function askDelete(a: PropertyAppliance) {
    setDeleteReason("");
    setConfirmingDelete(a);
  }

  async function reallyDelete(a: PropertyAppliance) {
    setWorking(true);
    setError("");
    try {
      await deleteAppliance(propertyId, a.id, deleteReason);
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

  function conditionLabel(v: string | null): string {
    if (!v) return "—";
    const found = CONDITION_OPTIONS.find((o) => o.value === v);
    return found ? found.label : v;
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
            + Add Appliance
          </button>
        </div>
      )}

      {canEdit && showAddForm && (
        <form
          onSubmit={handleAdd}
          className="bg-white border border-slate-200 rounded-xl p-5 mb-6"
        >
          <div className="text-sm font-semibold text-slate-700 mb-3">
            New Appliance
          </div>
          <ApplianceFields value={add} onChange={setAdd} />
          <div className="flex items-center gap-3 pt-4">
            <button
              type="submit"
              disabled={working || !add.name.trim()}
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
          No appliances yet.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Name
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Brand
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Model
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700">
                  Serial
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-24">
                  Condition
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-24">
                  Purchased
                </th>
                <th className="text-right px-3 py-2 font-medium text-slate-700 w-24">
                  Price
                </th>
                <th className="text-left px-3 py-2 font-medium text-slate-700 w-24">
                  Warranty
                </th>
                {canEdit && <th className="w-28"></th>}
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  {editingId === a.id ? (
                    <td colSpan={canEdit ? 9 : 8} className="px-3 py-3">
                      <ApplianceFields value={edit} onChange={setEdit} />
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
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {a.brand || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs font-mono">
                        {a.model_number || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs font-mono">
                        {a.serial_number || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {conditionLabel(a.condition)}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {a.purchase_date || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs text-right font-mono">
                        {money(a.purchase_price)}
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs">
                        {a.warranty_expires || "—"}
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
                  Remove appliance?
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

function ApplianceFields({
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
        <label className="block text-xs text-slate-500 mb-1">Name *</label>
        <input
          list="common-appliances"
          type="text"
          value={value.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="e.g. Refrigerator"
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
        <datalist id="common-appliances">
          {COMMON_APPLIANCES.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      </div>
      <div className="col-span-2">
        <label className="block text-xs text-slate-500 mb-1">Brand</label>
        <input
          type="text"
          value={value.brand}
          onChange={(e) => set("brand", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-2">
        <label className="block text-xs text-slate-500 mb-1">Model #</label>
        <input
          type="text"
          value={value.model_number}
          onChange={(e) => set("model_number", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-2">
        <label className="block text-xs text-slate-500 mb-1">Serial #</label>
        <input
          type="text"
          value={value.serial_number}
          onChange={(e) => set("serial_number", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">
          Condition
        </label>
        <select
          value={value.condition}
          onChange={(e) =>
            set(
              "condition",
              e.target.value as EditState["condition"]
            )
          }
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        >
          <option value="">— None —</option>
          {CONDITION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">
          Purchase date
        </label>
        <input
          type="date"
          value={value.purchase_date}
          onChange={(e) => set("purchase_date", e.target.value)}
          className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </div>
      <div className="col-span-3">
        <label className="block text-xs text-slate-500 mb-1">
          Purchase price
        </label>
        <input
          type="number"
          step="0.01"
          min="0"
          value={value.purchase_price}
          onChange={(e) => set("purchase_price", e.target.value)}
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
      <div className="col-span-3">
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