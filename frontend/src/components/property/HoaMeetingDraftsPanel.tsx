"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type MeetingDraft = {
  id: number; association_id: number; property_id: number;
  title: string; proposed_on: string; staff_agenda: string | null;
  status: "STAFF_DRAFT"; updated_at: string;
};

export default function HoaMeetingDraftsPanel({ associationId, propertyId, canEdit, onClose }: {
  associationId: number; propertyId: number; canEdit: boolean; onClose: () => void;
}) {
  const [items, setItems] = useState<MeetingDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [proposedOn, setProposedOn] = useState("");
  const [agenda, setAgenda] = useState("");
  const base = "/api/hoa/associations/" + associationId + "/meeting-drafts";

  useEffect(() => {
    let live = true;
    setLoading(true); setItems([]); setError(""); setMessage("");
    setEditingId(null); setTitle(""); setProposedOn(""); setAgenda("");
    void (async () => {
      try {
        const rows = await apiGet(
          "/api/hoa/associations/" + associationId + "/meeting-drafts?property_id=" + propertyId
        ) as MeetingDraft[];
        if (live) setItems(rows);
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "Meeting plans unavailable.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [associationId, propertyId]);

  function clearForm() {
    setEditingId(null); setTitle(""); setProposedOn(""); setAgenda("");
  }

  function edit(row: MeetingDraft) {
    setEditingId(row.id); setTitle(row.title);
    setProposedOn(row.proposed_on); setAgenda(row.staff_agenda || "");
    setError(""); setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !title.trim() || !proposedOn) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = {
        property_id: propertyId, title: title.trim(),
        proposed_on: proposedOn, staff_agenda: agenda.trim() || null,
      };
      const saved = editingId === null
        ? await apiPost(base, payload) as MeetingDraft
        : await apiPut(base + "/" + editingId, payload) as MeetingDraft;
      setItems((prior) => editingId === null
        ? [...prior, saved] : prior.map((row) => row.id === saved.id ? saved : row));
      clearForm();
      setMessage("Staff meeting plan saved. No official notice, vote or decision recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save meeting plan.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(row: MeetingDraft) {
    if (!canEdit || busy || !window.confirm(
      "Archive this staff plan? This is not an official board cancellation."
    )) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + row.id + "?property_id=" + propertyId);
      setItems((prior) => prior.filter((item) => item.id !== row.id));
      if (editingId === row.id) clearForm();
      setMessage("Staff meeting plan archived; no legal or financial effect.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive meeting plan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="w-full space-y-3 rounded-lg border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">HOA staff meeting plans</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-600">
        Planning metadata only. These entries are not official HOA meetings,
        statutory notices, board minutes, votes, quorum, board approval or
        governance authority. No attendee is certified and no charge is posted.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading planning drafts…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No staff meeting plans recorded for this property.</p>
      )}
      {!loading && items.map((row) => (
        <div key={row.id} className="flex flex-wrap items-start justify-between gap-2 rounded border bg-white p-3">
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium text-slate-900">{row.title}{" "}
              <span className="text-xs font-normal text-amber-700">STAFF DRAFT</span>
            </p>
            <p className="text-xs text-slate-500">Proposed date: {row.proposed_on}</p>
            {row.staff_agenda && <p className="mt-1 whitespace-pre-wrap break-words text-slate-600">{row.staff_agenda}</p>}
          </div>
          {canEdit && <div className="flex gap-3 text-sm">
            <button type="button" disabled={busy} onClick={() => edit(row)}
              className="text-blue-700 disabled:opacity-50">Edit</button>
            <button type="button" disabled={busy} onClick={() => { void archive(row); }}
              className="text-red-700 disabled:opacity-50">Archive</button>
          </div>}
        </div>
      ))}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-3 border-t pt-3">
          <h4 className="text-sm font-semibold">
            {editingId === null ? "Draft a meeting plan" : "Edit meeting plan"}
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">Staff plan title
              <input required maxLength={140} value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="block text-sm">Proposed date (not legal notice)
              <input required type="date" value={proposedOn}
                onChange={(event) => setProposedOn(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
          <label className="block text-sm">Tentative staff agenda (optional)
            <textarea maxLength={1000} rows={3} value={agenda}
              onChange={(event) => setAgenda(event.target.value)}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={busy || !title.trim() || !proposedOn}
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : editingId === null ? "Save staff plan" : "Update staff plan"}
            </button>
            {editingId !== null && <button type="button" disabled={busy} onClick={clearForm}
              className="rounded border px-3 py-2 text-sm">Cancel edit</button>}
          </div>
        </form>
      )}
    </section>
  );
}
