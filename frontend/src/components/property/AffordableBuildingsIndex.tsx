"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import Affordable8609Archive from "@/components/property/Affordable8609Archive";

type Building = { id: number; program_id: number; building_label: string; agency_bin: string };
type FormStatus = "NOT_RECORDED" | "FOLLOW_UP_NEEDED" | "REFERENCE_IDENTIFIED";
type FormReadiness = { building_id: number; status: FormStatus; updated_at: string | null };
export default function AffordableBuildingsIndex({
  propertyId, programId, canEdit, onClose,
}: { propertyId: number; programId: number; canEdit: boolean; onClose: () => void }) {
  const [rows, setRows] = useState<Building[]>([]);
  const [forms, setForms] = useState<Record<number, FormReadiness>>({});
  const [formBusy, setFormBusy] = useState<number | null>(null);
  const [archiveBuildingId, setArchiveBuildingId] = useState<number | null>(null);
  const [label, setLabel] = useState("");
  const [bin, setBin] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const path = `/api/properties/${propertyId}/affordable-programs/${programId}/buildings`;

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const data = await apiGet(path) as Building[];
        if (active) {
          setRows(data);
          const current = await Promise.all(data.map(async (row) => {
            const value = await apiGet(`${path}/${row.id}/8609-readiness`) as FormReadiness;
            return [row.id, value] as const;
          }));
          if (active) setForms(Object.fromEntries(current));
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Recorded buildings unavailable.");
      } finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [path]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const added = await apiPost(path, {
        building_label: label.trim(), agency_bin: bin.trim(),
      }) as Building;
      setRows((prev) => [...prev.filter((item) => item.id !== added.id), added]
        .sort((a, b) => a.agency_bin.localeCompare(b.agency_bin)));
      setLabel(""); setBin("");
      setMessage("Agency BIN recorded by staff; no Form 8609 or credit has been verified.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record this building.");
    } finally { setBusy(false); }
  }

  async function saveForm(id: number, status: FormStatus) {
    setFormBusy(id); setError(""); setMessage("");
    try {
      const result = await apiPut(`${path}/${id}/8609-readiness`, { status }) as FormReadiness;
      setForms((prev) => ({ ...prev, [id]: result }));
      setMessage("Staff Form 8609 reference status recorded. No IRS form or credit was verified.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot update Form 8609 reference.");
    } finally { setFormBusy(null); }
  }

  async function archive(id: number) {
    if (!window.confirm("Archive this recorded building ID? No agency filing will be changed.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(`${path}/${id}`);
      setRows((prev) => prev.filter((item) => item.id !== id));
      setArchiveBuildingId((prev) => prev === id ? null : prev);
      setMessage("Staff record archived. No tax filing was changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot archive this record.");
    } finally { setBusy(false); }
  }

  return (
    <section className="rounded-lg border border-slate-300 bg-slate-50 p-4" aria-label="Recorded LIHTC buildings">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">LIHTC building identification — staff record</h3>
        <button type="button" onClick={onClose} className="rounded border px-2 py-1 text-sm">Close</button>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Enter each agency-assigned Building Identification Number (BIN) separately.
        One property may have multiple LIHTC buildings. This inventory does not verify
        an issued Form 8609, agency allocation, tax-credit amount, owner election,
        certification or IRS filing. Form 8609 reference status is staff-entered metadata,
        not an agency-reviewed signed Form 8609 or an annual 8609-A. Do not enter taxpayer IDs or tenant information.
        See the{" "}
        <a href="https://www.irs.gov/instructions/i8609" target="_blank" rel="noopener noreferrer"
          className="underline">IRS Form 8609 instructions</a>.
      </p>
      {loading && <p className="mt-2 text-sm">Loading…</p>}
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-2 text-sm text-green-700">{message}</p>}
      {!loading && (
        <>
          <div className="mt-3 space-y-2">
            {rows.length === 0 && <p className="text-sm text-slate-500">No agency BINs recorded.</p>}
            {rows.map((row) => (
              <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded border bg-white p-3 text-sm">
                <span><strong>{row.building_label}</strong> — staff-entered BIN {row.agency_bin}</span>
                <label className="text-xs text-slate-700">Form 8609 reference (staff index only)
                  <select value={forms[row.id]?.status || "NOT_RECORDED"} disabled={!canEdit || formBusy !== null}
                    onChange={(event) => { void saveForm(row.id, event.target.value as FormStatus); }}
                    className="mt-1 block rounded border p-2">
                    <option value="NOT_RECORDED">Not recorded</option>
                    <option value="FOLLOW_UP_NEEDED">Follow-up needed</option>
                    <option value="REFERENCE_IDENTIFIED">Reference identified (not verified)</option>
                  </select>
                </label>
                {canEdit && <button type="button" onClick={() => setArchiveBuildingId((prior) => prior === row.id ? null : row.id)}
                  className="rounded border px-2 py-1 text-sm">Restricted Form 8609 scans</button>}
                {canEdit && <button type="button" disabled={busy} onClick={() => { void archive(row.id); }}
                  className="rounded border px-2 py-1 text-red-700 disabled:opacity-50">Archive</button>}
              </div>
            ))}
          </div>
          {archiveBuildingId !== null && canEdit && rows.some((item) => item.id === archiveBuildingId) && (
            <Affordable8609Archive propertyId={propertyId} programId={programId}
              buildingId={archiveBuildingId} onClose={() => setArchiveBuildingId(null)} />
          )}
          {canEdit && <form onSubmit={(event) => { void save(event); }} className="mt-4 grid gap-3 border-t pt-3 md:grid-cols-3">
            <label className="text-xs text-slate-700">Building label
              <input required maxLength={100} value={label}
                onChange={(event) => setLabel(event.target.value)}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-xs text-slate-700">Agency-assigned BIN
              <input required maxLength={40} value={bin}
                onChange={(event) => setBin(event.target.value)}
                placeholder="Example: OH-20-12345 (or OH2012345)"
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <button type="submit" disabled={busy || !label.trim() || !bin.trim()}
              className="self-end rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : "Record building BIN"}
            </button>
          </form>}
        </>
      )}
    </section>
  );
}
