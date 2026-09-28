"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Observation = {
  id: number;
  association_id: number;
  property_id: number;
  summary: string;
  observed_on: string;
  details: string | null;
  status: "STAFF_RECORDED";
  updated_at: string;
};

export default function HoaObservationsPanel({ associationId, propertyId, canEdit, onClose }: {
  associationId: number; propertyId: number; canEdit: boolean; onClose: () => void;
}) {
  const [items, setItems] = useState<Observation[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [summary, setSummary] = useState("");
  const [observedOn, setObservedOn] = useState("");
  const [details, setDetails] = useState("");
  const base = "/api/hoa/associations/" + associationId + "/observations";

  useEffect(() => {
    let live = true;
    setItems([]); setLoading(true); setError(""); setMessage("");
    setEditingId(null); setSummary(""); setObservedOn(""); setDetails("");
    void (async () => {
      try {
        const records = await apiGet(
          "/api/hoa/associations/" + associationId + "/observations?property_id=" + propertyId
        ) as Observation[];
        if (live) setItems(records);
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "Observations unavailable.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [associationId, propertyId]);

  function clearForm() {
    setEditingId(null); setSummary(""); setObservedOn(""); setDetails("");
  }

  function edit(row: Observation) {
    setEditingId(row.id); setSummary(row.summary);
    setObservedOn(row.observed_on); setDetails(row.details || "");
    setError(""); setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !summary.trim() || !observedOn) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = {
        property_id: propertyId, summary: summary.trim(),
        observed_on: observedOn, details: details.trim() || null,
      };
      const saved = editingId === null
        ? await apiPost(base, payload) as Observation
        : await apiPut(base + "/" + editingId, payload) as Observation;
      setItems((prior) => editingId === null
        ? [...prior, saved] : prior.map((row) => row.id === saved.id ? saved : row));
      clearForm();
      setMessage("Staff observation saved. No legal violation, notice, fine, or charge was issued.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save observation.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(row: Observation) {
    if (!canEdit || busy || !window.confirm(
      "Archive this staff record? No legal violation is decided by this action."
    )) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + row.id + "?property_id=" + propertyId);
      setItems((prior) => prior.filter((item) => item.id !== row.id));
      if (editingId === row.id) clearForm();
      setMessage("Staff observation archived; no accounting or legal status changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive observation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="w-full space-y-3 rounded-lg border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">HOA staff observations</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-600">
        These are unverified staff observations, not adjudicated violations, legal notices,
        cure deadlines, hearings, fines, tenant obligations, assessments, or GL postings.
        This panel does not send notices or create charges.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading observations…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No staff observations recorded for this property.</p>
      )}
      {!loading && items.map((row) => (
        <div key={row.id} className="flex flex-wrap items-start justify-between gap-2 rounded border bg-white p-3">
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium text-slate-900">{row.summary}{" "}
              <span className="text-xs font-normal text-amber-700">STAFF RECORDED</span>
            </p>
            <p className="text-xs text-slate-500">Observed: {row.observed_on}</p>
            {row.details && <p className="mt-1 whitespace-pre-wrap break-words text-slate-600">{row.details}</p>}
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
          <h4 className="text-sm font-semibold">
            {editingId === null ? "Record staff observation" : "Edit staff observation"}
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">Observation summary
              <input required maxLength={240} value={summary}
                onChange={(event) => setSummary(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="block text-sm">Date observed
              <input required type="date" value={observedOn}
                onChange={(event) => setObservedOn(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
          <label className="block text-sm">Staff details (optional)
            <textarea maxLength={1000} rows={3} value={details}
              onChange={(event) => setDetails(event.target.value)}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={busy || !summary.trim() || !observedOn}
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : editingId === null ? "Save staff record" : "Update staff record"}
            </button>
            {editingId !== null && <button type="button" disabled={busy} onClick={clearForm}
              className="rounded border px-3 py-2 text-sm">Cancel edit</button>}
          </div>
        </form>
      )}
    </section>
  );
}
