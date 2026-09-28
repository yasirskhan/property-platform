"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Kind = "RECURRING" | "SPECIAL";
type Frequency = "MONTHLY" | "QUARTERLY" | "ANNUAL" | "ONE_TIME";
type Proposal = {
  id: number;
  association_id: number;
  property_id: number;
  title: string;
  assessment_type: Kind;
  frequency: Frequency;
  proposed_amount: string;
  proposed_first_on: string;
  proposed_through: string | null;
  status: "DRAFT";
  updated_at: string;
};

export default function HoaDraftAssessmentsPanel({
  associationId, propertyId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; canEdit: boolean; onClose: () => void;
}) {
  const [items, setItems] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<Kind>("RECURRING");
  const [frequency, setFrequency] = useState<Frequency>("MONTHLY");
  const [amount, setAmount] = useState("");
  const [firstOn, setFirstOn] = useState("");
  const [through, setThrough] = useState("");
  const base = "/api/hoa/associations/" + associationId + "/draft-assessments";

  useEffect(() => {
    let live = true;
    setLoading(true); setError(""); setItems([]);
    void (async () => {
      try {
        const rows = await apiGet(
          "/api/hoa/associations/" + associationId +
          "/draft-assessments?property_id=" + propertyId
        ) as Proposal[];
        if (live) setItems(rows);
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "Drafts unavailable.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [associationId, propertyId]);

  function clearForm() {
    setEditingId(null);
    setTitle(""); setKind("RECURRING"); setFrequency("MONTHLY");
    setAmount(""); setFirstOn(""); setThrough("");
  }

  function edit(row: Proposal) {
    setEditingId(row.id);
    setTitle(row.title); setKind(row.assessment_type);
    setFrequency(row.frequency); setAmount(String(row.proposed_amount));
    setFirstOn(row.proposed_first_on); setThrough(row.proposed_through || "");
    setError(""); setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !title.trim() || !amount || !firstOn) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = {
        property_id: propertyId,
        title: title.trim(),
        assessment_type: kind,
        frequency: kind === "SPECIAL" ? "ONE_TIME" : frequency,
        proposed_amount: amount,
        proposed_first_on: firstOn,
        proposed_through: through || null,
      };
      const row = editingId === null
        ? await apiPost(base, payload) as Proposal
        : await apiPut(base + "/" + editingId, payload) as Proposal;
      setItems((previous) => editingId === null
        ? [...previous, row]
        : previous.map((item) => item.id === row.id ? row : item));
      clearForm();
      setMessage("Staff-only draft saved. No payment is due and no charge was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save draft.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(row: Proposal) {
    if (!canEdit || !window.confirm("Archive this planning draft? No accounting entry will be created.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + row.id + "?property_id=" + propertyId);
      setItems((previous) => previous.filter((item) => item.id !== row.id));
      if (editingId === row.id) clearForm();
      setMessage("Draft archived. No legal assessment or financial transaction was changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive draft.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="w-full space-y-3 rounded-lg border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">Assessment planning drafts</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-600">
        Proposed amounts and dates are staff assumptions only. DRAFT is never
        an HOA bill, authorized assessment, payment obligation, tenant charge,
        board approval, reserve movement, or general-ledger posting.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading planning drafts…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No assessment planning drafts for this property.</p>
      )}
      {!loading && items.map((row) => (
        <div key={row.id} className="flex flex-wrap items-start justify-between gap-2 rounded border bg-white p-3">
          <div className="text-sm text-slate-700">
            <div className="font-medium text-slate-900">{row.title} <span className="text-amber-700">DRAFT</span></div>
            <p>{row.assessment_type === "SPECIAL" ? "Special, one-time" : "Recurring, " + row.frequency.toLowerCase()}
              {" · "}Proposed ${row.proposed_amount}
            </p>
            <p className="text-xs text-slate-500">
              Proposed first date: {row.proposed_first_on}
              {row.proposed_through ? " · Proposed through: " + row.proposed_through : ""}
            </p>
          </div>
          {canEdit && (
            <div className="flex gap-3 text-sm">
              <button type="button" disabled={busy} onClick={() => edit(row)}
                className="text-blue-700 disabled:opacity-50">Edit</button>
              <button type="button" disabled={busy} onClick={() => { void archive(row); }}
                className="text-red-700 disabled:opacity-50">Archive</button>
            </div>
          )}
        </div>
      ))}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-3 border-t pt-3">
          <h4 className="text-sm font-semibold">{editingId === null ? "Add a planning draft" : "Edit planning draft"}</h4>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">Proposal title
              <input required maxLength={120} value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="block text-sm">Proposal type
              <select value={kind}
                onChange={(event) => {
                  const next = event.target.value as Kind;
                  setKind(next); setFrequency(next === "SPECIAL" ? "ONE_TIME" : "MONTHLY");
                }}
                className="mt-1 block w-full rounded border p-2">
                <option value="RECURRING">Recurring proposal</option>
                <option value="SPECIAL">One-time special proposal</option>
              </select>
            </label>
            {kind === "RECURRING" && (
              <label className="block text-sm">Proposed frequency
                <select value={frequency} onChange={(event) => setFrequency(event.target.value as Frequency)}
                  className="mt-1 block w-full rounded border p-2">
                  <option value="MONTHLY">Monthly</option>
                  <option value="QUARTERLY">Quarterly</option>
                  <option value="ANNUAL">Annual</option>
                </select>
              </label>
            )}
            <label className="block text-sm">Proposed amount (not billed)
              <input required min="0.01" step="0.01" type="number" value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="block text-sm">Proposed first date (not a due date)
              <input required type="date" value={firstOn}
                onChange={(event) => setFirstOn(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="block text-sm">Proposed through (optional)
              <input type="date" min={firstOn || undefined} value={through}
                onChange={(event) => setThrough(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={busy || !title.trim() || !amount || !firstOn}
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : editingId === null ? "Save draft only" : "Update draft only"}
            </button>
            {editingId !== null && (
              <button type="button" onClick={clearForm}
                className="rounded border px-3 py-2 text-sm">Cancel edit</button>
            )}
          </div>
        </form>
      )}
    </section>
  );
}
