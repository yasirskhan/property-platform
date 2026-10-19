"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";

type UnitChoice = { id: number; property_name: string; unit_number: string };
type ChecklistItem = { area: string; condition: string; notes: string };
const CHECKLIST_AREAS = ["PLUMBING", "ELECTRICAL", "HVAC", "APPLIANCES", "SAFETY"] as const;
type Inspection = {
  id: number; property_id: number; unit_id: number;
  property_name?: string | null; unit_number?: string | null;
  inspection_date: string; recorded_condition: string;
  findings: string; checklist_items?: ChecklistItem[]; recorded_by_id: number | null;
};

export default function InspectionRecordsPage() {
  const [records, setRecords] = useState<Inspection[]>([]);
  const [units, setUnits] = useState<UnitChoice[]>([]);
  const [unitId, setUnitId] = useState("");
  const [unitSearch, setUnitSearch] = useState("");
  const [unitsLoading, setUnitsLoading] = useState(true);
  const [unitError, setUnitError] = useState("");
  const [inspectionDate, setInspectionDate] = useState("");
  const [condition, setCondition] = useState("NOT_ASSESSED");
  const [findings, setFindings] = useState("");
  const [checklist, setChecklist] = useState<Record<string, string>>({});
  const [checklistNotes, setChecklistNotes] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState("");
  const [conditionFilter, setConditionFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [activeFilters, setActiveFilters] = useState("");


  useEffect(() => {
    let active = true;
    apiGet("/work-orders/request-units?limit=100")
      .then((rows: UnitChoice[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected unit response.");
        if (active) setUnits(rows);
      })
      .catch((cause) => {
        if (active) setUnitError(cause instanceof Error ? cause.message : "Units unavailable.");
      })
      .finally(() => { if (active) setUnitsLoading(false); });
    apiGet("/api/unit-inspections?limit=100")
      .then((rows: Inspection[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected inspection response.");
        if (active) {
          setRecords(rows);
          setNextOffset(rows.length);
          setHasMore(rows.length === 100);
        }
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Inspections unavailable.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function searchUnits(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (unitsLoading) return;
    setUnitsLoading(true); setUnitError(""); setUnitId(""); setUnits([]);
    try {
      const search = unitSearch.trim();
      const query = search ? `&search=${encodeURIComponent(search)}` : "";
      const rows = await apiGet(`/work-orders/request-units?limit=100${query}`) as UnitChoice[];
      if (!Array.isArray(rows)) throw new Error("Unexpected unit response.");
      setUnits(rows);
    } catch (cause) {
      setUnitError(cause instanceof Error ? cause.message : "Unit search failed.");
    } finally {
      setUnitsLoading(false);
    }
  }

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true); setMoreError("");
    try {
      const rows = await apiGet(`/api/unit-inspections?limit=100&offset=${nextOffset}${activeFilters}`) as Inspection[];
      if (!Array.isArray(rows)) throw new Error("Unexpected inspection response.");
      setRecords((previous) => {
        const seen = new Set(previous.map((entry) => entry.id));
        return [...previous, ...rows.filter((entry) => !seen.has(entry.id))];
      });
      setNextOffset((previous) => previous + rows.length);
      setHasMore(rows.length === 100);
    } catch (cause) {
      setMoreError(cause instanceof Error ? cause.message : "More inspections unavailable.");
    } finally {
      setLoadingMore(false);
    }
  }

  async function applyHistoryFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setError("Start date cannot be after end date.");
      return;
    }
    const params = new URLSearchParams();
    if (conditionFilter) params.set("recorded_condition", conditionFilter);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    const filters = params.toString() ? `&${params.toString()}` : "";
    setLoading(true); setError(""); setMoreError("");
    try {
      const rows = await apiGet(`/api/unit-inspections?limit=100${filters}`) as Inspection[];
      if (!Array.isArray(rows)) throw new Error("Unexpected inspection response.");
      setRecords(rows);
      setNextOffset(rows.length);
      setHasMore(rows.length === 100);
      setActiveFilters(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Inspection filtering failed.");
    } finally {
      setLoading(false);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || !units.some((u) => String(u.id) === unitId)) {
      setError("Select a unit available to inspection staff.");
      return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const created = await apiPost("/api/unit-inspections", {
        unit_id: Number(unitId), inspection_date: inspectionDate,
        recorded_condition: condition, findings: findings.trim(),
        checklist_items: CHECKLIST_AREAS.map((area) => ({area, condition: checklist[area] || "NOT_ASSESSED", notes: (checklistNotes[area] || "").trim()})),
      }) as Inspection;
      if (!created || typeof created.id !== "number") {
        throw new Error("Unexpected inspection save response.");
      }
      // The 201 response is authoritative. A second GET failing must not
      // report a successfully persisted inspection as a failed submission.
      const matchesCondition = !conditionFilter || created.recorded_condition === conditionFilter;
      const matchesDates = (!dateFrom || created.inspection_date >= dateFrom)
        && (!dateTo || created.inspection_date <= dateTo);
      setRecords((previous) => matchesCondition && matchesDates
        ? [created, ...previous.filter((row) => row.id !== created.id)] : previous);
      setFindings("");
      setChecklist({});
      setChecklistNotes({});
      setNotice("Inspection evidence recorded and audited.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Inspection could not be recorded.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/maintenance/work-orders" className="text-sm text-blue-800 hover:underline">
        Back to Maintenance
      </Link>
      <header>
        <h1 className="text-2xl font-semibold">Inspection records</h1>
        <p className="mt-1 text-sm text-slate-600">
          Manually recorded staff inspection evidence. This is not the planned
          mobile checklist, offline capture, or photo-inspection workflow.
        </p>
      </header>
      {error && <p role="alert" className="rounded-lg border p-3 text-sm text-red-700">{error}</p>}
      {loading && <p className="text-sm text-slate-600">Loading inspection records…</p>}
      {notice && <p role="status" className="rounded-lg border p-3 text-sm">{notice}</p>}
      {!loading && !error && (
        <form onSubmit={(event) => void searchUnits(event)} className="space-y-2 rounded-xl border bg-white p-5">
          <label className="block text-sm">Find an active unit by property name or unit number
            <input aria-label="Search inspection units" maxLength={80} value={unitSearch}
              onChange={(event) => setUnitSearch(event.target.value)}
              placeholder="Property or unit number"
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <button type="submit" disabled={unitsLoading}
            className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
            {unitsLoading ? "Searching…" : "Find units"}
          </button>
          {unitError && <p role="alert" className="text-sm text-red-700">{unitError}</p>}
          {!unitsLoading && !unitError && units.length === 0 &&
            <p className="text-sm text-slate-600">No matching active units found.</p>}
          <p className="text-xs text-slate-600">Showing up to 100 matching units. Refine the search to find more.</p>
        </form>
      )}
      {!loading && !error && (
        <form onSubmit={(event) => void save(event)} className="space-y-3 rounded-xl border bg-white p-5">
          <h2 className="font-semibold">Record a dated inspection</h2>
          <label className="block text-sm">Unit
            <select required disabled={unitsLoading} aria-label="Inspection unit" value={unitId}
              onChange={(event) => setUnitId(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2">
              <option value="">Select an active unit</option>
              {units.map((u) => <option value={u.id} key={u.id}>
                {u.property_name} · Unit {u.unit_number}
              </option>)}
            </select>
          </label>
          <label className="block text-sm">Inspection date
            <input required type="date" aria-label="Inspection date"
              max={new Date().toISOString().slice(0, 10)}
              value={inspectionDate} onChange={(event) => setInspectionDate(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <label className="block text-sm">Recorded condition
            <select aria-label="Inspection condition" value={condition}
              onChange={(event) => setCondition(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2">
              <option value="NOT_ASSESSED">Not assessed</option>
              <option value="SATISFACTORY">Satisfactory</option>
              <option value="ATTENTION_NEEDED">Attention needed</option>
            </select>
          </label>
          <fieldset className="space-y-2 rounded-lg border p-3">
            <legend className="px-1 text-sm font-semibold">Inspection checklist</legend>
            {CHECKLIST_AREAS.map((area) => <label className="block text-sm" key={area}>{area.replaceAll("_", " ")}
              <select aria-label={`${area} condition`} value={checklist[area] || "NOT_ASSESSED"}
                onChange={(event) => setChecklist((prev) => ({ ...prev, [area]: event.target.value }))}
                className="mt-1 w-full rounded-lg border p-2">
                <option value="NOT_ASSESSED">Not assessed</option>
                <option value="SATISFACTORY">Satisfactory</option>
                <option value="ATTENTION_NEEDED">Attention needed</option>
              </select>
              <input aria-label={`${area} notes`} maxLength={500}
                value={checklistNotes[area] || ""}
                onChange={(event) => setChecklistNotes((prev) => ({ ...prev, [area]: event.target.value }))}
                placeholder="Optional checklist notes" className="mt-1 w-full rounded-lg border p-2" />
            </label>)}
          </fieldset>
          <label className="block text-sm">Findings
            <textarea aria-label="Inspection findings" maxLength={2000} rows={3}
              value={findings} onChange={(event) => setFindings(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <button disabled={saving || unitsLoading || !unitId || !inspectionDate}
            type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
            {saving ? "Saving…" : "Save inspection record"}
          </button>
        </form>
      )}
      {!loading && !error && (
        <section className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold">Recorded inspections</h2>
          <form onSubmit={(event) => void applyHistoryFilters(event)} className="mt-3 grid gap-3 md:grid-cols-4">
            <label className="text-sm">Condition
              <select aria-label="Filter inspection condition" value={conditionFilter}
                onChange={(event) => setConditionFilter(event.target.value)} className="mt-1 w-full rounded-lg border p-2">
                <option value="">All conditions</option>
                <option value="SATISFACTORY">Satisfactory</option>
                <option value="ATTENTION_NEEDED">Attention needed</option>
                <option value="NOT_ASSESSED">Not assessed</option>
              </select>
            </label>
            <label className="text-sm">From date
              <input type="date" aria-label="Inspection history start date" value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)} className="mt-1 w-full rounded-lg border p-2" />
            </label>
            <label className="text-sm">Through date
              <input type="date" aria-label="Inspection history end date" value={dateTo}
                onChange={(event) => setDateTo(event.target.value)} className="mt-1 w-full rounded-lg border p-2" />
            </label>
            <button type="submit" disabled={loading} className="self-end rounded-lg border px-4 py-2 text-sm disabled:opacity-50">Filter history</button>
          </form>
          {records.length === 0 ? <p className="mt-3 text-sm">No staff-recorded inspections yet.</p>
            : <ul className="mt-3 space-y-3">
                {records.map((row) => (
                  <li key={row.id} className="rounded-lg border p-3 text-sm">
                    <p className="font-medium"><Link href={`/dashboard/maintenance/staff-inspection-records/${row.id}`} className="text-blue-800 hover:underline">Inspection #{row.id}</Link> · {row.property_name || `Property #${row.property_id}`}
                      · Unit {row.unit_number || `#${row.unit_id}`}
                      · {row.inspection_date} · {row.recorded_condition.replaceAll("_", " ")}</p>
                    <p className="mt-1 whitespace-pre-wrap">{row.findings || "No findings noted."}</p>
                    {!!row.checklist_items?.length && <ul className="mt-2 space-y-1">
                      {row.checklist_items.map((item) => <li key={item.area}>
                        {item.area.replaceAll("_", " ")}: {item.condition.replaceAll("_", " ")}
                        {item.notes ? ` · ${item.notes}` : ""}
                      </li>)}
                    </ul>}
                    <p className="mt-1 text-xs text-slate-500">Recorded by user #{row.recorded_by_id ?? "unknown"}</p>
                  </li>
                ))}
              </ul>}
          {hasMore && <button type="button" disabled={loadingMore}
            onClick={() => void loadMore()}
            className="mt-3 rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
            {loadingMore ? "Loading more…" : "Load older inspections"}
          </button>}
          {moreError && <p role="alert" className="mt-2 text-sm text-red-700">{moreError}</p>}
        </section>
      )}
    </div>
  );
}
