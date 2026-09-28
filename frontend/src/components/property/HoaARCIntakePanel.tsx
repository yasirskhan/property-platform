"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import HoaARCApplicationsPanel from "@/components/property/HoaARCApplicationsPanel";

type Intake = {
  id: number; association_id: number; property_id: number;
  project_title: string; staff_noted_on: string; staff_description: string | null;
  status: "STAFF_INTAKE"; updated_at: string;
};

export default function HoaARCIntakePanel({ associationId, propertyId, canEdit, onClose }: {
  associationId: number; propertyId: number; canEdit: boolean; onClose: () => void;
}) {
  const [items, setItems] = useState<Intake[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [workflowId, setWorkflowId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [notedOn, setNotedOn] = useState("");
  const [description, setDescription] = useState("");
  const base = "/api/hoa/associations/" + associationId + "/arc-intakes";

  useEffect(() => {
    let live = true;
    setLoading(true); setItems([]); setError(""); setMessage("");
    setEditingId(null); setWorkflowId(null); setTitle(""); setNotedOn(""); setDescription("");
    void (async () => {
      try {
        const rows = await apiGet(
          "/api/hoa/associations/" + associationId + "/arc-intakes?property_id=" + propertyId
        ) as Intake[];
        if (live) setItems(rows);
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "ARC staff intake unavailable.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [associationId, propertyId]);

  function clearForm() {
    setEditingId(null); setTitle(""); setNotedOn(""); setDescription("");
  }

  function edit(row: Intake) {
    setEditingId(row.id); setTitle(row.project_title);
    setNotedOn(row.staff_noted_on); setDescription(row.staff_description || "");
    setError(""); setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !title.trim() || !notedOn) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = {
        property_id: propertyId, project_title: title.trim(),
        staff_noted_on: notedOn, staff_description: description.trim() || null,
      };
      const saved = editingId === null
        ? await apiPost(base, payload) as Intake
        : await apiPut(base + "/" + editingId, payload) as Intake;
      setItems((prior) => editingId === null
        ? [...prior, saved] : prior.map((row) => row.id === saved.id ? saved : row));
      clearForm();
      setMessage("Staff interest recorded. No ARC application or decision was issued.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save staff ARC intake.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(row: Intake) {
    if (!canEdit || busy || !window.confirm(
      "Archive this staff note? No architectural approval or denial is affected."
    )) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + row.id + "?property_id=" + propertyId);
      setItems((prior) => prior.filter((item) => item.id !== row.id));
      if (editingId === row.id) clearForm();
      if (workflowId === row.id) setWorkflowId(null);
      setMessage("Staff intake archived; no legal or financial action taken.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive staff ARC intake.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="w-full space-y-3 rounded-lg border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">ARC staff project intake</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-600">
        This is an internal staff project note, not a submitted ARC application,
        architectural approval or denial, governing-document verification,
        construction permit, review deadline, HOA fee or assessed charge.
        It does not notify applicants or the association.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading staff entries…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No architectural project interest recorded for this property.</p>
      )}
      {!loading && items.map((row) => (
        <div key={row.id} className="flex flex-wrap items-start justify-between gap-2 rounded border bg-white p-3">
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium text-slate-900">{row.project_title}{" "}
              <span className="text-xs font-normal text-amber-700">STAFF INTAKE</span>
            </p>
            <p className="text-xs text-slate-500">Staff noted: {row.staff_noted_on}</p>
            {row.staff_description && <p className="mt-1 whitespace-pre-wrap break-words text-slate-600">{row.staff_description}</p>}
          </div>
          <div className="flex gap-3 text-sm">
            <button type="button" onClick={() => setWorkflowId((old) => old === row.id ? null : row.id)}
              className="text-blue-700">Application workflow</button>
          {canEdit && <>
            <button type="button" disabled={busy} onClick={() => edit(row)}
              className="text-blue-700 disabled:opacity-50">Edit</button>
            <button type="button" disabled={busy} onClick={() => { void archive(row); }}
              className="text-red-700 disabled:opacity-50">Archive</button>
          </>}
          </div>
          {workflowId === row.id && <HoaARCApplicationsPanel
            associationId={associationId} propertyId={propertyId} intakeId={row.id}
            projectTitle={row.project_title} canEdit={canEdit}
            onClose={() => setWorkflowId(null)} /> }
        </div>
      ))}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-3 border-t pt-3">
          <h4 className="text-sm font-semibold">
            {editingId === null ? "Record project interest" : "Edit staff project note"}
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">Project title
              <input required maxLength={140} value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="block text-sm">Date noted by staff
              <input required type="date" value={notedOn}
                onChange={(event) => setNotedOn(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
          <label className="block text-sm">Staff project description (optional)
            <textarea maxLength={1000} rows={3} value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={busy || !title.trim() || !notedOn}
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : editingId === null ? "Save staff intake" : "Update staff intake"}
            </button>
            {editingId !== null && <button type="button" disabled={busy} onClick={clearForm}
              className="rounded border px-3 py-2 text-sm">Cancel edit</button>}
          </div>
        </form>
      )}
    </section>
  );
}
