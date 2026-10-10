"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import AffordableInterestLog from "@/components/property/AffordableInterestLog";
import AffordableEvidenceChecklist from "@/components/property/AffordableEvidenceChecklist";
import AffordableBuildingsIndex from "@/components/property/AffordableBuildingsIndex";

type ProgramType = "SECTION_8_VOUCHER" | "SECTION_8_PROJECT_BASED" | "LIHTC" | "HUD_OTHER" | "OTHER";
type Program = {
  id: number;
  property_id: number;
  program_type: ProgramType;
  label: string;
  agency_name: string | null;
  recorded_start: string | null;
  recorded_end: string | null;
};
type Draft = {
  program_type: ProgramType;
  label: string;
  agency_name: string;
  recorded_start: string;
  recorded_end: string;
};
const blank: Draft = {
  program_type: "LIHTC", label: "", agency_name: "", recorded_start: "", recorded_end: "",
};
const types: Record<ProgramType, string> = {
  LIHTC: "Low-Income Housing Tax Credit (LIHTC)",
  SECTION_8_VOUCHER: "Section 8 — voucher program (staff recorded)",
  SECTION_8_PROJECT_BASED: "Section 8 — project-based (staff recorded)",
  HUD_OTHER: "Other HUD program (staff recorded)",
  OTHER: "Other affordable housing program",
};

export default function AffordableProgramsTab({
  propertyId, canEdit,
}: { propertyId: number; canEdit: boolean }) {
  const [items, setItems] = useState<Program[]>([]);
  const [draft, setDraft] = useState<Draft>(blank);
  const [editing, setEditing] = useState<number | null>(null);
  const [interestProgramId, setInterestProgramId] = useState<number | null>(null);
  const [evidenceProgramId, setEvidenceProgramId] = useState<number | null>(null);
  const [buildingsProgramId, setBuildingsProgramId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    setItems([]); setLoading(true); setError(""); setMessage("");
    void (async () => {
      try {
        const result = await apiGet(`/api/properties/${propertyId}/affordable-programs`) as Program[];
        if (active) setItems(result);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Program inventory unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [propertyId]);

  function reset() {
    setDraft(blank); setEditing(null);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError(""); setMessage("");
    if (draft.recorded_start && draft.recorded_end && draft.recorded_start > draft.recorded_end) {
      setError("Recorded end date cannot precede start date.");
      return;
    }
    setBusy(true);
    const payload = {
      program_type: draft.program_type, label: draft.label.trim(),
      agency_name: draft.agency_name.trim() || null,
      recorded_start: draft.recorded_start || null,
      recorded_end: draft.recorded_end || null,
    };
    try {
      if (editing === null) {
        const added = await apiPost(`/api/properties/${propertyId}/affordable-programs`, payload) as Program;
        setItems((prev) => [...prev, added]);
      } else {
        const changed = await apiPut(`/api/properties/${propertyId}/affordable-programs/${editing}`, payload) as Program;
        setItems((prev) => prev.map((item) => item.id === changed.id ? changed : item));
      }
      reset();
      setMessage("Staff-recorded program details saved; eligibility has not been certified.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot save program details.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(id: number) {
    if (!window.confirm("Archive this recorded program? This does not terminate any assistance.")) return;
    setError(""); setMessage(""); setBusy(true);
    try {
      await apiDelete(`/api/properties/${propertyId}/affordable-programs/${id}`);
      setItems((prev) => prev.filter((item) => item.id !== id));
      if (editing === id) reset();
      setMessage("Staff-recorded program archived; no assistance was changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot archive program.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 rounded-xl border bg-white p-5">
      <h2 className="text-lg font-semibold text-slate-900">Affordable housing — program inventory</h2>
      <p className="text-sm text-slate-600">
        Record which programs staff associate with this property. These entries are not
        HUD certifications, LIHTC elections, verified Section 8 participation or a
        determination of tenant eligibility. Income, AMI limits, HAP payments,
        compliance deadlines and tenant charges are not calculated here.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading recorded programs…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No programs recorded. This does not establish that the property has no regulatory obligations.</p>
      )}
      {!loading && items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="border-b">
              <th className="p-2">Staff label</th>
              <th className="p-2">Recorded program</th>
              <th className="p-2">Recorded agency</th>
              <th className="p-2">Recorded dates</th>
              {canEdit && <th className="p-2">Actions</th>}
            </tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b">
                  <td className="p-2">{item.label}
                    <button type="button" onClick={() => setInterestProgramId(item.id)}
                      className="ml-2 text-xs text-blue-700 underline">Interest</button>
                    <button type="button" onClick={() => setEvidenceProgramId(item.id)}
                      className="ml-2 text-xs text-blue-700 underline">Readiness checklist</button>
                    {item.program_type === "LIHTC" && <button type="button"
                      onClick={() => setBuildingsProgramId(item.id)}
                      className="ml-2 text-xs text-blue-700 underline">Recorded LIHTC buildings</button>}
                  </td>
                  <td className="p-2">{types[item.program_type]}</td>
                  <td className="p-2">{item.agency_name || "Not recorded"}</td>
                  <td className="p-2">{item.recorded_start || "—"} – {item.recorded_end || "—"}</td>
                  {canEdit && <td className="p-2">
                    <button type="button" disabled={busy} className="mr-3 text-blue-700 disabled:opacity-50"
                      onClick={() => { setEditing(item.id); setDraft({
                        program_type: item.program_type, label: item.label,
                        agency_name: item.agency_name || "", recorded_start: item.recorded_start || "",
                        recorded_end: item.recorded_end || "",
                      }); setError(""); setMessage(""); }}>Edit</button>
                    <button type="button" disabled={busy} className="text-red-700 disabled:opacity-50"
                      onClick={() => { void archive(item.id); }}>Archive</button>
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {buildingsProgramId !== null && (
        <AffordableBuildingsIndex key={buildingsProgramId} propertyId={propertyId}
          programId={buildingsProgramId} canEdit={canEdit}
          onClose={() => setBuildingsProgramId(null)} />
      )}
      {evidenceProgramId !== null && (
        <AffordableEvidenceChecklist key={evidenceProgramId} propertyId={propertyId}
          programId={evidenceProgramId} canEdit={canEdit}
          onClose={() => setEvidenceProgramId(null)} />
      )}
      {interestProgramId !== null && (
        <AffordableInterestLog key={interestProgramId} propertyId={propertyId}
          programId={interestProgramId} canEdit={canEdit}
          onClose={() => setInterestProgramId(null)} />
      )}
      {canEdit && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-3 border-t pt-4">
          <h3 className="text-sm font-semibold">{editing === null ? "Record a program" : "Update recorded program"}</h3>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm">Program category
              <select value={draft.program_type}
                onChange={(event) => setDraft((p) => ({ ...p, program_type: event.target.value as ProgramType }))}
                className="mt-1 block w-full rounded border p-2">
                {Object.entries(types).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </label>
            <label className="text-sm">Staff program label
              <input required maxLength={120} value={draft.label}
                onChange={(event) => setDraft((p) => ({ ...p, label: event.target.value }))}
                className="mt-1 block w-full rounded border p-2"
                placeholder="Program reference used by staff" />
            </label>
            <label className="text-sm">Recorded administering agency (optional)
              <input maxLength={160} value={draft.agency_name}
                onChange={(event) => setDraft((p) => ({ ...p, agency_name: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm">Recorded start date (optional)
              <input type="date" value={draft.recorded_start}
                onChange={(event) => setDraft((p) => ({ ...p, recorded_start: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm">Recorded end date (optional)
              <input type="date" value={draft.recorded_end}
                onChange={(event) => setDraft((p) => ({ ...p, recorded_end: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
          <p className="text-xs text-slate-500">
            Enter only property program identifiers; do not enter tenant income,
            household details, SSNs or W-9 data. Dates are staff records, not compliance deadlines.
          </p>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={busy || !draft.label.trim()}
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              {busy ? "Saving…" : editing === null ? "Save recorded program" : "Update recorded program"}
            </button>
            {editing !== null && <button type="button" onClick={reset}
              className="rounded border px-4 py-2 text-sm">Cancel edit</button>}
          </div>
        </form>
      )}
    </section>
  );
}
