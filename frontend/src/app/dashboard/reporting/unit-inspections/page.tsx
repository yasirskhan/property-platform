"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ReportActions from "@/components/reporting/ReportActions";
import { apiGet, apiPost } from "@/lib/api";

type Property = { id: number; name: string; is_active: boolean };
type Unit = { id: number; unit_number: string; is_active: boolean };
type Preview = { title: string; headers: string[]; rows: (string | number)[][]; total: number };
type Inspection = { id: number; unit_id: number; inspection_date: string; recorded_condition: string; findings: string };
type Condition = "SATISFACTORY" | "ATTENTION_NEEDED" | "NOT_ASSESSED";

export default function UnitInspectionsPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [propertyId, setPropertyId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [inspectionDate, setInspectionDate] = useState("");
  const [condition, setCondition] = useState<Condition>("NOT_ASSESSED");
  const [findings, setFindings] = useState("");
  const [records, setRecords] = useState<Inspection[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    apiGet("/properties")
      .then((items: Property[]) => setProperties(items.filter((p) => p.is_active)))
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Cannot load property list."));
  }, []);

  useEffect(() => {
    if (!propertyId) { setUnits([]); setUnitId(""); setRecords([]); return; }
    let active = true;
    setUnits([]); setUnitId("");
    Promise.all([
      apiGet(`/properties/${propertyId}/units`) as Promise<Unit[]>,
      apiGet(`/api/unit-inspections?property_id=${propertyId}`) as Promise<Inspection[]>,
    ]).then(([items, saved]) => {
      if (!active) return;
      setUnits(items.filter((unit) => unit.is_active));
      setRecords(saved);
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Unit inspection records unavailable.");
    });
    return () => { active = false; };
  }, [propertyId]);

  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const saved = await apiPost("/api/unit-inspections", {
        unit_id: Number(unitId), inspection_date: inspectionDate,
        recorded_condition: condition, findings: findings.trim(),
      }) as Inspection;
      setRecords((prior) => [saved, ...prior]);
      setPreview(null); setApplied({});
      setFindings("");
      setMessage("Staff-entered inspection record saved. This does not certify an independent inspection.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot save inspection record.");
    } finally { setBusy(false); }
  }

  async function load() {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const params: Record<string, string> = propertyId ? { property_id: propertyId } : {};
    const query = new URLSearchParams(params).toString();
    try {
      const data = await apiGet(`/api/reporting/unit-inspections/preview${query ? "?" + query : ""}`) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Inspection report unavailable.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Unit Inspection Report</h1>
        <p className="mt-1 text-sm text-slate-600">
          Only staff-entered dated inspection records appear. An empty report means
          no inspection record exists, not that a unit passed inspection.
          Mobile/offline inspections, photos and formal checklists are Phase 5 work.
        </p>
      </header>
      <section className="rounded-xl border bg-white p-4">
        <h2 className="font-semibold">Record a dated inspection observation</h2>
        <p className="my-2 text-sm text-slate-500">Enter only observations actually made. Records are append-only and audited.</p>
        <form onSubmit={(event) => { void save(event); }} className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <label className="block text-sm">Property
              <select required value={propertyId} onChange={(event) => { setPropertyId(event.target.value); setPreview(null); }}
                className="mt-1 block min-w-40 rounded border p-2">
                <option value="">Select property</option>
                {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label className="block text-sm">Unit
              <select required value={unitId} onChange={(event) => setUnitId(event.target.value)}
                className="mt-1 block min-w-32 rounded border p-2">
                <option value="">Select unit</option>
                {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.unit_number}</option>)}
              </select>
            </label>
            <label className="block text-sm">Inspection date
              <input required type="date" value={inspectionDate}
                max={new Date().toISOString().slice(0, 10)}
                onChange={(event) => setInspectionDate(event.target.value)}
                className="mt-1 block rounded border p-2" />
            </label>
            <label className="block text-sm">Recorded condition
              <select value={condition} onChange={(event) => setCondition(event.target.value as Condition)}
                className="mt-1 block rounded border p-2">
                <option value="NOT_ASSESSED">Not assessed</option>
                <option value="SATISFACTORY">Satisfactory (staff-entered)</option>
                <option value="ATTENTION_NEEDED">Attention needed (staff-entered)</option>
              </select>
            </label>
          </div>
          <label className="block text-sm">Recorded findings (optional)
            <textarea value={findings} maxLength={2000}
              onChange={(event) => setFindings(event.target.value)}
              rows={3} className="mt-1 block w-full rounded border p-2" />
          </label>
          <button type="submit" disabled={busy || !unitId || !inspectionDate}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
            {busy ? "Saving…" : "Save recorded inspection"}
          </button>
        </form>
        {records.length > 0 && (
          <p className="mt-3 text-xs text-slate-500">
            {records.length} explicitly recorded observation{records.length === 1 ? "" : "s"} on this property.
          </p>
        )}
      </section>
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <section className="space-y-3">
        <button type="button" disabled={busy} onClick={() => void load()}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load inspection report"}
        </button>
        {preview && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
              <span>{preview.total} staff-recorded inspection entries.</span>
              <ReportActions reportKey="property.unit_inspection" parameters={applied} />
            </div>
            <div className="overflow-x-auto rounded-xl border bg-white">
              <table className="min-w-[1000px] w-full text-sm">
                <thead className="bg-slate-50"><tr>
                  {preview.headers.map((h) => (
                    <th key={h} scope="col" className="px-3 py-2 text-left font-semibold">{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i} className="border-t">
                      {row.map((value, j) => <td key={j} className="px-3 py-2">{String(value)}</td>)}
                    </tr>
                  ))}
                  {preview.total === 0 && <tr><td colSpan={preview.headers.length}
                    className="p-5 text-center text-slate-500">
                    No inspection observations recorded in this scope; no inspection outcome can be inferred.
                  </td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
