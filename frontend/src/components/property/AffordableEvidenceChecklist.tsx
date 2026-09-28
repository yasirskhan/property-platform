"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPut } from "@/lib/api";

type Category = "AGENCY_GUIDANCE" | "PROGRAM_AGREEMENT" | "PROPERTY_RECORD_INDEX" | "INSPECTION_COORDINATION";
type Status = "NOT_RECORDED" | "FOLLOW_UP_NEEDED" | "REFERENCE_IDENTIFIED";
type Item = { category: Category; status: Status; staff_follow_up_on: string | null; updated_at: string | null };
const labels: Record<Category, string> = {
  AGENCY_GUIDANCE: "Agency or program guidance reference",
  PROGRAM_AGREEMENT: "Program agreement reference",
  PROPERTY_RECORD_INDEX: "Property-level records index",
  INSPECTION_COORDINATION: "Inspection coordination reference",
};
const statuses: Record<Status, string> = {
  NOT_RECORDED: "Not recorded",
  FOLLOW_UP_NEEDED: "Staff follow-up needed",
  REFERENCE_IDENTIFIED: "Staff identified a reference (not verified)",
};

export default function AffordableEvidenceChecklist({
  propertyId, programId, canEdit, onClose,
}: { propertyId: number; programId: number; canEdit: boolean; onClose: () => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<Category | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [inspectionSummary, setInspectionSummary] = useState<{ total_recorded: number; latest_recorded_on: string | null } | null>(null);
  const [inspectionError, setInspectionError] = useState("");
  const [inspectionBusy, setInspectionBusy] = useState(false);
  const path = `/api/properties/${propertyId}/affordable-programs/${programId}/evidence`;
  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const rows = await apiGet(path) as Item[];
        if (live) setItems(rows);
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "Evidence index unavailable.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [path]);

  async function save(item: Item, status: Status, date: string | null) {
    setBusy(item.category); setError(""); setMessage("");
    try {
      const saved = await apiPut(path, {
        category: item.category, status, staff_follow_up_on: date || null,
      }) as Item;
      setItems((prev) => prev.map((row) => row.category === saved.category ? saved : row));
      setMessage("Staff readiness index updated. No regulatory compliance decision was made.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update readiness.");
    } finally { setBusy(null); }
  }

  return (
    <section className="rounded-lg border border-slate-300 bg-slate-50 p-4" aria-label="Program evidence readiness">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">Program evidence readiness — staff index</h3>
        <button type="button" onClick={onClose} className="rounded border px-2 py-1 text-sm">Close</button>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Staff records only whether a reference has been identified. These statuses do not
        certify eligibility, agency approval, inspections, LIHTC compliance, or
        a statutory deadline. Do not enter household information, income, SSNs
        or signed forms here. Use existing property attachments only for
        ordinary non-sensitive property documents under their own access rules.
      </p>
      <div className="mt-3 border-t pt-3 text-sm">
        <button type="button" disabled={inspectionBusy} onClick={() => {
          setInspectionBusy(true); setInspectionError(""); setInspectionSummary(null);
          void (async () => {
            try {
              const result = await apiGet(`${path.slice(0, -"/evidence".length)}/inspection-summary`) as {
                total_recorded: number; latest_recorded_on: string | null;
              };
              setInspectionSummary(result);
            } catch {
              setInspectionError("A separate unit-inspection permission is required to view this summary.");
            } finally { setInspectionBusy(false); }
          })();
        }} className="rounded border px-3 py-1.5 text-blue-700 disabled:opacity-50">
          {inspectionBusy ? "Checking…" : "Cross-reference staff-recorded unit inspections"}
        </button>
        {inspectionError && <p role="status" className="mt-2 text-amber-800">{inspectionError}</p>}
        {inspectionSummary && (
          <p className="mt-2 text-slate-600">
            Existing property-wide inspection entries: {inspectionSummary.total_recorded}.
            Latest recorded date: {inspectionSummary.latest_recorded_on || "None"}.
            These entries are not linked to this program and do not prove HQS or LIHTC compliance.{" "}
            <Link className="underline" href="/dashboard/reporting/unit-inspections">Open Unit Inspection report</Link>.
          </p>
        )}
      </div>
      {loading && <p className="mt-2 text-sm">Loading…</p>}
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-2 text-sm text-green-700">{message}</p>}
      {!loading && <div className="mt-3 space-y-3">
        {items.map((item) => (
          <div key={item.category} className="grid gap-2 rounded-lg border bg-white p-3 md:grid-cols-3">
            <p className="text-sm font-medium">{labels[item.category]}</p>
            <label className="text-xs text-slate-700">
              Recorded status
              <select value={item.status} disabled={!canEdit || busy !== null}
                onChange={(event) => { void save(item, event.target.value as Status, item.staff_follow_up_on); }}
                className="mt-1 block w-full rounded border p-2">
                {Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-700">
              Staff follow-up date (not a legal due date)
              <input type="date" value={item.staff_follow_up_on || ""}
                disabled={!canEdit || busy !== null}
                onChange={(event) => { void save(item, item.status, event.target.value || null); }}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
        ))}
      </div>}
    </section>
  );
}
