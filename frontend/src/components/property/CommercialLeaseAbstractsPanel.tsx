"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiFetch, apiGet, apiPost, apiPut } from "@/lib/api";
import CommercialLeaseTermsPanel from "@/components/property/CommercialLeaseTermsPanel";

type Candidate = {
  lease_id: number;
  unit_id: number;
  unit_number: string;
  lease_start_on: string;
  lease_end_on: string;
  lease_status: string;
};
type SourceOption = {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  source_status: "PRIVATE_STAFF_ATTACHMENT";
};
type Reference = Candidate & {
  id: number;
  property_id: number;
  rent_commencement_on: string | null;
  source_attachment_id: number | null;
  source_filename: string | null;
  source_status: "STAFF_LINKED_UNVERIFIED" | null;
  reference_status: "STAFF_RECORDED_UNVERIFIED";
};

export default function CommercialLeaseAbstractsPanel({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [references, setReferences] = useState<Reference[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState("");
  const [recordedDate, setRecordedDate] = useState("");
  const [dates, setDates] = useState<Record<number, string>>({});
  const [sourceOptions, setSourceOptions] = useState<Record<number, SourceOption[]>>({});
  const [sourceIds, setSourceIds] = useState<Record<number, string>>({});
  const [newSources, setNewSources] = useState<SourceOption[]>([]);
  const [newSourceId, setNewSourceId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = `/api/properties/${propertyId}/commercial-lease-abstracts`;

  async function reload() {
    const [saved, eligible] = await Promise.all([
      apiGet(base) as Promise<Reference[]>,
      apiGet(base + "/candidates") as Promise<Candidate[]>,
    ]);
    setReferences(saved);
    setCandidates(eligible);
    setDates(Object.fromEntries(saved.map((item) => [
      item.id, item.rent_commencement_on || "",
    ])));
    setSourceIds(Object.fromEntries(saved.map((item) => [
      item.id, item.source_attachment_id ? String(item.source_attachment_id) : "",
    ])));
  }

  async function loadSources(leaseId: number, forNew = false) {
    const options = await apiGet(
      base + "/source-candidates?lease_id=" + leaseId,
    ) as SourceOption[];
    if (forNew) setNewSources(options);
    else setSourceOptions((prior) => ({ ...prior, [leaseId]: options }));
  }

  async function downloadSource(row: Reference) {
    if (!row.source_attachment_id) return;
    const response = await apiFetch(
      "/api/attachments/download/" + row.source_attachment_id,
      { method: "GET" },
    );
    if (!response.ok) throw new Error("Private lease source document unavailable.");
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = row.source_filename || "commercial-lease-source";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(href);
  }

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    void Promise.all([
      apiGet(base) as Promise<Reference[]>,
      apiGet(base + "/candidates") as Promise<Candidate[]>,
    ]).then(([saved, eligible]) => {
      if (!live) return;
      setReferences(saved);
      setCandidates(eligible);
      setDates(Object.fromEntries(saved.map((item) => [
        item.id, item.rent_commencement_on || "",
      ])));
      setSourceIds(Object.fromEntries(saved.map((item) => [
        item.id, item.source_attachment_id ? String(item.source_attachment_id) : "",
      ])));
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Commercial records unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [base]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !selected || busy) return;
    setBusy(true);
    setError(""); setMessage("");
    try {
      await apiPost(base, {
        lease_id: Number(selected),
        rent_commencement_on: recordedDate || null,
        source_attachment_id: newSourceId ? Number(newSourceId) : null,
      });
      setSelected(""); setRecordedDate(""); setNewSourceId(""); setNewSources([]);
      await reload();
      setMessage("Staff reference recorded. This is not a billing instruction.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record reference.");
    } finally {
      setBusy(false);
    }
  }

  async function update(row: Reference) {
    if (!canEdit || busy) return;
    setBusy(true);
    setError(""); setMessage("");
    try {
      await apiPut(base + "/" + row.id, {
        rent_commencement_on: dates[row.id] || null,
        source_attachment_id: sourceIds[row.id] ? Number(sourceIds[row.id]) : null,
      });
      await reload();
      setMessage("Staff-recorded date updated. Lease and invoices remain unchanged.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update reference.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(row: Reference) {
    if (!canEdit || busy || !window.confirm("Archive this staff reference? The lease will not be changed.")) return;
    setBusy(true);
    setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + row.id);
      await reload();
      setMessage("Reference archived. No lease, charge, or ledger record was changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive reference.");
    } finally {
      setBusy(false);
    }
  }

  const unrecorded = candidates.filter((item) => !references.some((row) => row.lease_id === item.lease_id));

  return (
    <section className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="text-lg font-semibold text-slate-900">Commercial lease commencement references</h2>
      <p className="text-sm text-slate-600">
        Only staff-recorded references to existing leases. The lease start date comes from
        the recorded lease; the separate rent commencement date is an unverified staff entry.
        Neither is proof of executed contract terms. No rent, CAM, NNN, percentage rent,
        notice, charge, invoice or general ledger entry is generated here.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading references…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && references.length === 0 && (
        <p className="text-sm text-slate-500">No staff commencement references recorded.</p>
      )}
      {!loading && references.map((row) => (
        <div key={row.id} className="space-y-2 rounded-lg border p-3 text-sm">
          <div className="font-medium text-slate-900">Unit {row.unit_number} · Recorded lease #{row.lease_id}</div>
          <div className="text-xs text-slate-600">
            Recorded lease start: {row.lease_start_on} · End: {row.lease_end_on} · Status: {row.lease_status}
          </div>
          <div className="text-xs text-slate-600">
            Staff reference: {row.reference_status.replaceAll("_", " ")}
          </div>
          <div className="text-xs text-slate-600">
            Source document: {row.source_filename || "Not linked"}
            {row.source_status ? " · " + row.source_status.replaceAll("_", " ") : ""}
          </div>
          <CommercialLeaseTermsPanel
            propertyId={propertyId}
            abstractId={row.id}
            sourceAttachmentId={row.source_attachment_id}
            canEdit={canEdit}
          />
          {row.source_attachment_id && <button type="button" disabled={busy}
            onClick={() => { void downloadSource(row).catch((cause) =>
              setError(cause instanceof Error ? cause.message : "Source unavailable.")); }}
            className="text-blue-700 disabled:opacity-50">
            Download private lease source
          </button>}
          {canEdit ? (
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-xs">Staff-recorded rent commencement
                <input type="date" value={dates[row.id] || ""}
                  onChange={(event) => setDates((prior) => ({
                    ...prior, [row.id]: event.target.value,
                  }))}
                  className="mt-1 block rounded border p-2 text-sm" />
              </label>
              <button type="button" disabled={busy}
                onClick={() => { void loadSources(row.lease_id).catch((cause) =>
                  setError(cause instanceof Error ? cause.message : "Source list unavailable.")); }}
                className="rounded border px-3 py-2 text-blue-700 disabled:opacity-50">
                Choose private source
              </button>
              {sourceOptions[row.lease_id] && <label className="text-xs">Private lease source
                <select value={sourceIds[row.id] || ""}
                  onChange={(event) => setSourceIds((prior) => ({ ...prior, [row.id]: event.target.value }))}
                  className="mt-1 block rounded border p-2 text-sm">
                  <option value="">No source linked</option>
                  {sourceOptions[row.lease_id].map((item) =>
                    <option key={item.id} value={item.id}>{item.filename}</option>)}
                </select>
              </label>}
              <button type="button" disabled={busy} onClick={() => { void update(row); }}
                className="rounded border px-3 py-2 text-blue-700 disabled:opacity-50">Save reference</button>
              <button type="button" disabled={busy} onClick={() => { void archive(row); }}
                className="rounded border px-3 py-2 text-red-700 disabled:opacity-50">Archive</button>
            </div>
          ) : (
            <p className="text-sm text-slate-600">
              Staff-recorded rent commencement: {row.rent_commencement_on || "Not recorded"}
            </p>
          )}
        </div>
      ))}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void create(event); }} className="space-y-2 border-t pt-3">
          <h3 className="text-sm font-semibold">Record a lease reference</h3>
          <label className="block text-sm">Existing recorded lease
            <select required value={selected} onChange={(event) => {
                const value = event.target.value;
                setSelected(value);
                setNewSourceId("");
                setNewSources([]);
                if (value) void loadSources(Number(value), true).catch((cause) =>
                  setError(cause instanceof Error ? cause.message : "Source list unavailable."));
              }}
              className="mt-1 block w-full rounded border p-2">
              <option value="">Select a lease on this commercial property</option>
              {unrecorded.map((item) => (
                <option key={item.lease_id} value={item.lease_id}>
                  {item.unit_number} · Lease #{item.lease_id} · {item.lease_status}
                </option>
              ))}
            </select>
          </label>
          {selected && <label className="block text-sm">Private lease source document (optional)
            <select value={newSourceId} onChange={(event) => setNewSourceId(event.target.value)}
              className="mt-1 block w-full rounded border p-2">
              <option value="">No private source linked</option>
              {newSources.map((item) =>
                <option key={item.id} value={item.id}>{item.filename}</option>)}
            </select>
          </label>}
          <label className="block text-sm">Staff-recorded rent commencement (optional)
            <input type="date" value={recordedDate}
              onChange={(event) => setRecordedDate(event.target.value)}
              className="mt-1 block rounded border p-2" />
          </label>
          <button type="submit" disabled={!selected || busy}
            className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
            {busy ? "Saving…" : "Record staff reference"}
          </button>
        </form>
      )}
    </section>
  );
}
