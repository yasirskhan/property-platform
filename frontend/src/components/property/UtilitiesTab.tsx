"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";

// ------------------------------------------------------------
// Types
// ------------------------------------------------------------
type Utility = {
  id: number;
  property_id: number;
  utility_type: string;
  company_name: string;
  company_phone: string | null;
  company_website: string | null;
  paid_by: string;
  account_number: string | null;
  account_holder_name: string | null;
  setup_instructions: string | null;
  internal_notes: string | null;
  is_active: boolean;
};

type Bill = {
  id: number;
  utility_id: number;
  billing_period_start: string | null;
  billing_period_end: string | null;
  due_date: string | null;
  amount: string;
  paid_at: string | null;
  notes: string | null;
};

type TrashSchedule = {
  id: number;
  property_id: number;
  pickup_type: string;
  day_of_week: string;
  frequency: string;
  time_window: string | null;
  notes: string | null;
  is_active: boolean;
};

const UTILITY_TYPES = [
  { value: "electric", label: "Electric", icon: "⚡" },
  { value: "gas", label: "Gas", icon: "🔥" },
  { value: "water", label: "Water", icon: "💧" },
  { value: "sewer", label: "Sewer", icon: "🚰" },
  { value: "trash", label: "Trash", icon: "🗑️" },
  { value: "internet", label: "Internet", icon: "🌐" },
  { value: "cable", label: "Cable", icon: "📺" },
  { value: "other", label: "Other", icon: "🔧" },
];

const PAID_BY_LABELS: Record<string, string> = {
  tenant: "Tenant pays directly",
  owner: "Owner pays",
  included_in_rent: "Included in rent",
  shared: "Shared",
};

const PICKUP_TYPES = [
  { value: "trash", label: "Trash" },
  { value: "recycling", label: "Recycling" },
  { value: "yard_waste", label: "Yard Waste" },
  { value: "bulk", label: "Bulk" },
];

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// ------------------------------------------------------------
// Main Component
// ------------------------------------------------------------
export default function UtilitiesTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [utilities, setUtilities] = useState<Utility[]>([]);
  const [trash, setTrash] = useState<TrashSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUtilityForm, setShowUtilityForm] = useState(false);
  const [editingUtilityId, setEditingUtilityId] = useState<number | null>(null);
  const [showTrashForm, setShowTrashForm] = useState(false);
  const [editingTrashId, setEditingTrashId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [u, t] = await Promise.all([
        apiGet(`/properties/${propertyId}/utilities`).catch(() => []),
        apiGet(`/properties/${propertyId}/trash-schedule`).catch(() => []),
      ]);
      setUtilities(u);
      setTrash(t);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  async function deleteUtility(id: number) {
    if (!confirm("Delete this utility?")) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/properties/${propertyId}/utilities/${id}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Delete failed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function deleteTrash(id: number) {
    if (!confirm("Delete this pickup schedule?")) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/properties/${propertyId}/trash-schedule/${id}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Delete failed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (loading) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="space-y-8">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* UTILITIES SECTION */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900">Utility Companies</h3>
          {canEdit && (
            <button
              onClick={() => {
                setEditingUtilityId(null);
                setShowUtilityForm(true);
              }}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + Add Utility
            </button>
          )}
        </div>

        {showUtilityForm && (
          <UtilityForm
            propertyId={propertyId}
            utilityId={editingUtilityId}
            onCancel={() => {
              setShowUtilityForm(false);
              setEditingUtilityId(null);
            }}
            onSaved={() => {
              setShowUtilityForm(false);
              setEditingUtilityId(null);
              load();
            }}
          />
        )}

        {utilities.length === 0 && !showUtilityForm ? (
          <p className="text-slate-500 text-sm">No utilities added yet.</p>
        ) : (
          <div className="space-y-3">
            {utilities.map((u) => (
              <UtilityCard
                key={u.id}
                utility={u}
                canEdit={canEdit}
                onEdit={() => {
                  setEditingUtilityId(u.id);
                  setShowUtilityForm(true);
                }}
                onDelete={() => deleteUtility(u.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* TRASH PICKUP SECTION */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900">Trash & Recycling Pickup</h3>
          {canEdit && (
            <button
              onClick={() => {
                setEditingTrashId(null);
                setShowTrashForm(true);
              }}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + Add Pickup
            </button>
          )}
        </div>

        {showTrashForm && (
          <TrashForm
            propertyId={propertyId}
            scheduleId={editingTrashId}
            onCancel={() => {
              setShowTrashForm(false);
              setEditingTrashId(null);
            }}
            onSaved={() => {
              setShowTrashForm(false);
              setEditingTrashId(null);
              load();
            }}
          />
        )}

        {trash.length === 0 && !showTrashForm ? (
          <p className="text-slate-500 text-sm">No pickup schedule yet.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {trash.map((s) => (
              <div key={s.id} className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium text-slate-900 capitalize">
                      {s.pickup_type.replace("_", " ")}
                    </p>
                    <p className="text-sm text-slate-600">
                      {s.day_of_week} · {s.frequency}
                    </p>
                    {s.time_window && (
                      <p className="text-xs text-slate-500 mt-1">{s.time_window}</p>
                    )}
                    {s.notes && (
                      <p className="text-xs text-slate-500 mt-1">{s.notes}</p>
                    )}
                  </div>
                  {canEdit && (
                    <div className="flex gap-1">
                      <button
                        onClick={() => {
                          setEditingTrashId(s.id);
                          setShowTrashForm(true);
                        }}
                        className="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-50"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => deleteTrash(s.id)}
                        className="text-xs px-2 py-1 border border-red-200 text-red-700 rounded hover:bg-red-50"
                      >
                        ×
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------
// UTILITY CARD
// ------------------------------------------------------------
function UtilityCard({
  utility,
  canEdit,
  onEdit,
  onDelete,
}: {
  utility: Utility;
  canEdit: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [showBills, setShowBills] = useState(false);
  const [bills, setBills] = useState<Bill[]>([]);
  const [billsLoading, setBillsLoading] = useState(false);
  const [showBillForm, setShowBillForm] = useState(false);

  const meta = UTILITY_TYPES.find((t) => t.value === utility.utility_type);
  const isOwnerPaid =
    utility.paid_by === "owner" || utility.paid_by === "included_in_rent";

  async function loadBills() {
    setBillsLoading(true);
    try {
      const data = await apiGet(
        `/properties/${utility.property_id}/utilities/${utility.id}/bills`
      );
      setBills(data);
    } catch {
      setBills([]);
    } finally {
      setBillsLoading(false);
    }
  }

  async function toggleBills() {
    if (!showBills) await loadBills();
    setShowBills(!showBills);
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xl">{meta?.icon || "🔧"}</span>
            <div>
              <p className="font-medium text-slate-900">{utility.company_name}</p>
              <p className="text-xs text-slate-500 uppercase tracking-wide">
                {meta?.label || utility.utility_type}
              </p>
            </div>
          </div>

          <div className="mt-2 text-sm text-slate-600 space-y-0.5">
            <p className="font-medium text-slate-700">
              {PAID_BY_LABELS[utility.paid_by] || utility.paid_by}
            </p>
            {utility.company_phone && <p>📞 {utility.company_phone}</p>}
            {utility.company_website && (
              <p>
                🔗{" "}
                <a
                  href={utility.company_website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  {utility.company_website}
                </a>
              </p>
            )}
            {utility.account_number && (
              <p className="text-slate-500">Account #: {utility.account_number}</p>
            )}
            {utility.setup_instructions && (
              <p className="text-slate-500 italic">{utility.setup_instructions}</p>
            )}
          </div>
        </div>

        {canEdit && (
          <div className="flex gap-1 ml-4">
            <button
              onClick={onEdit}
              className="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-50"
            >
              Edit
            </button>
            <button
              onClick={onDelete}
              className="text-xs px-2 py-1 border border-red-200 text-red-700 rounded hover:bg-red-50"
            >
              ×
            </button>
          </div>
        )}
      </div>

      {isOwnerPaid && canEdit && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <button
            onClick={toggleBills}
            className="text-xs text-slate-600 hover:text-slate-900"
          >
            {showBills ? "▼ Hide bills" : "▶ Show bills"} ({bills.length})
          </button>

          {showBills && (
            <div className="mt-3 space-y-2">
              {!showBillForm && (
                <button
                  onClick={() => setShowBillForm(true)}
                  className="text-xs px-3 py-1 bg-slate-100 rounded hover:bg-slate-200"
                >
                  + Add Bill
                </button>
              )}

              {showBillForm && (
                <BillForm
                  propertyId={utility.property_id}
                  utilityId={utility.id}
                  onCancel={() => setShowBillForm(false)}
                  onSaved={() => {
                    setShowBillForm(false);
                    loadBills();
                  }}
                />
              )}

              {billsLoading ? (
                <p className="text-xs text-slate-500">Loading…</p>
              ) : bills.length === 0 ? (
                <p className="text-xs text-slate-500">No bills recorded.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 text-left">
                      <th className="py-1">Period</th>
                      <th className="py-1">Amount</th>
                      <th className="py-1">Paid</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {bills.map((b) => (
                      <tr key={b.id}>
                        <td className="py-1 text-slate-700">
                          {b.billing_period_start || "—"} → {b.billing_period_end || "—"}
                        </td>
                        <td className="py-1 text-slate-900 font-medium font-mono">
                          {formatMoney(b.amount)}
                        </td>
                        <td className="py-1 text-slate-500">{b.paid_at || "unpaid"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// UTILITY FORM
// ------------------------------------------------------------
function UtilityForm({
  propertyId,
  utilityId,
  onCancel,
  onSaved,
}: {
  propertyId: number;
  utilityId: number | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [utilityType, setUtilityType] = useState("electric");
  const [companyName, setCompanyName] = useState("");
  const [companyPhone, setCompanyPhone] = useState("");
  const [companyWebsite, setCompanyWebsite] = useState("");
  const [paidBy, setPaidBy] = useState("tenant");
  const [accountNumber, setAccountNumber] = useState("");
  const [accountHolderName, setAccountHolderName] = useState("");
  const [setupInstructions, setSetupInstructions] = useState("");
  const [internalNotes, setInternalNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (utilityId === null) return;
    apiGet(`/properties/${propertyId}/utilities/${utilityId}`).then((u) => {
      setUtilityType(u.utility_type || "electric");
      setCompanyName(u.company_name || "");
      setCompanyPhone(u.company_phone || "");
      setCompanyWebsite(u.company_website || "");
      setPaidBy(u.paid_by || "tenant");
      setAccountNumber(u.account_number || "");
      setAccountHolderName(u.account_holder_name || "");
      setSetupInstructions(u.setup_instructions || "");
      setInternalNotes(u.internal_notes || "");
    });
  }, [utilityId, propertyId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        utility_type: utilityType,
        company_name: companyName,
        company_phone: companyPhone || null,
        company_website: companyWebsite || null,
        paid_by: paidBy,
        account_number: accountNumber || null,
        account_holder_name: accountHolderName || null,
        setup_instructions: setupInstructions || null,
        internal_notes: internalNotes || null,
      };

      const token = localStorage.getItem("token");
      const url = utilityId
        ? `http://127.0.0.1:8000/properties/${propertyId}/utilities/${utilityId}`
        : `http://127.0.0.1:8000/properties/${propertyId}/utilities`;
      const method = utilityId ? "PATCH" : "POST";

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
        {utilityId ? "Edit Utility" : "New Utility"}
      </h4>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Utility Type</label>
          <select value={utilityType} onChange={(e) => setUtilityType(e.target.value)} className="input">
            {UTILITY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.icon} {t.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Company Name</label>
          <input
            type="text"
            required
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Austin Energy"
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Phone</label>
          <input
            type="text"
            value={companyPhone}
            onChange={(e) => setCompanyPhone(e.target.value)}
            placeholder="(512) 555-1234"
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Website</label>
          <input
            type="text"
            value={companyWebsite}
            onChange={(e) => setCompanyWebsite(e.target.value)}
            placeholder="austinenergy.com"
            className="input"
          />
        </div>

        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">Who Pays?</label>
          <select value={paidBy} onChange={(e) => setPaidBy(e.target.value)} className="input">
            <option value="tenant">Tenant pays directly (they set up their own account)</option>
            <option value="owner">Owner pays (you track bills)</option>
            <option value="included_in_rent">Included in rent</option>
            <option value="shared">Shared with other units</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Account # (internal)</label>
          <input
            type="text"
            value={accountNumber}
            onChange={(e) => setAccountNumber(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Account Holder (internal)</label>
          <input
            type="text"
            value={accountHolderName}
            onChange={(e) => setAccountHolderName(e.target.value)}
            className="input"
          />
        </div>

        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Setup Instructions (shown to tenant)
          </label>
          <textarea
            value={setupInstructions}
            onChange={(e) => setSetupInstructions(e.target.value)}
            rows={2}
            placeholder="Set up your own account at austinenergy.com"
            className="input"
          />
        </div>

        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Internal Notes (not shown to tenant)
          </label>
          <textarea
            value={internalNotes}
            onChange={(e) => setInternalNotes(e.target.value)}
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
          {saving ? "Saving…" : utilityId ? "Update" : "Add Utility"}
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

// ------------------------------------------------------------
// BILL FORM
// ------------------------------------------------------------
function BillForm({
  propertyId,
  utilityId,
  onCancel,
  onSaved,
}: {
  propertyId: number;
  utilityId: number;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [paidAt, setPaidAt] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        amount: Number(amount),
        billing_period_start: periodStart || null,
        billing_period_end: periodEnd || null,
        due_date: dueDate || null,
        paid_at: paidAt || null,
        notes: notes || null,
      };
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/properties/${propertyId}/utilities/${utilityId}/bills`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        }
      );
      if (!res.ok) throw new Error("Save failed");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-3 space-y-2 text-xs">
      {error && <p className="text-red-600">{error}</p>}
      <div className="grid grid-cols-2 gap-2">
        <input
          type="number"
          step="0.01"
          required
          placeholder="Amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="input"
        />
        <input
          type="date"
          placeholder="Paid on"
          value={paidAt}
          onChange={(e) => setPaidAt(e.target.value)}
          className="input"
        />
        <input
          type="date"
          placeholder="Period start"
          value={periodStart}
          onChange={(e) => setPeriodStart(e.target.value)}
          className="input"
        />
        <input
          type="date"
          placeholder="Period end"
          value={periodEnd}
          onChange={(e) => setPeriodEnd(e.target.value)}
          className="input"
        />
        <input
          type="date"
          placeholder="Due date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
          className="input col-span-2"
        />
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="px-3 py-1 bg-slate-900 text-white rounded hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Add Bill"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1 border border-slate-300 rounded hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ------------------------------------------------------------
// TRASH SCHEDULE FORM
// ------------------------------------------------------------
function TrashForm({
  propertyId,
  scheduleId,
  onCancel,
  onSaved,
}: {
  propertyId: number;
  scheduleId: number | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [pickupType, setPickupType] = useState("trash");
  const [dayOfWeek, setDayOfWeek] = useState("Monday");
  const [frequency, setFrequency] = useState("weekly");
  const [timeWindow, setTimeWindow] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (scheduleId === null) return;
    apiGet(`/properties/${propertyId}/trash-schedule`).then((list) => {
      const s = list.find((x: TrashSchedule) => x.id === scheduleId);
      if (s) {
        setPickupType(s.pickup_type);
        setDayOfWeek(s.day_of_week);
        setFrequency(s.frequency);
        setTimeWindow(s.time_window || "");
        setNotes(s.notes || "");
      }
    });
  }, [scheduleId, propertyId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        pickup_type: pickupType,
        day_of_week: dayOfWeek,
        frequency,
        time_window: timeWindow || null,
        notes: notes || null,
      };
      const token = localStorage.getItem("token");
      const url = scheduleId
        ? `http://127.0.0.1:8000/properties/${propertyId}/trash-schedule/${scheduleId}`
        : `http://127.0.0.1:8000/properties/${propertyId}/trash-schedule`;
      const method = scheduleId ? "PATCH" : "POST";
      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Save failed");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-50 rounded-xl border border-slate-200 p-6 mb-4 space-y-4">
      <h4 className="font-semibold text-slate-900">
        {scheduleId ? "Edit Pickup Schedule" : "New Pickup Schedule"}
      </h4>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Pickup Type</label>
          <select value={pickupType} onChange={(e) => setPickupType(e.target.value)} className="input">
            {PICKUP_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Day of Week</label>
          <select value={dayOfWeek} onChange={(e) => setDayOfWeek(e.target.value)} className="input">
            {DAYS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Frequency</label>
          <select value={frequency} onChange={(e) => setFrequency(e.target.value)} className="input">
            <option value="weekly">Weekly</option>
            <option value="biweekly">Bi-Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Time Window</label>
          <input
            type="text"
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value)}
            placeholder="Before 7:00 AM"
            className="input"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Notes (shown to tenant)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="Bins must be at curb by 6:00 AM"
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
          {saving ? "Saving…" : scheduleId ? "Update" : "Add Pickup"}
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