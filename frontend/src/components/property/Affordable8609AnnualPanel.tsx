"use client";
import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";

type Category = "BUILDING_OR_ACQUISITION" | "REHABILITATION";
type Status = "NOT_RECORDED" | "FOLLOW_UP_NEEDED" | "REFERENCE_IDENTIFIED";
type Item = { building_id: number; tax_year: number; allocation_category: Category; status: Status; updated_at: string | null };
const labels: Record<Category, string> = {
  BUILDING_OR_ACQUISITION: "Building / acquisition",
  REHABILITATION: "Rehabilitation (separate annual form)",
};
const choices: Record<Status, string> = {
  NOT_RECORDED: "Not recorded",
  FOLLOW_UP_NEEDED: "Follow-up needed",
  REFERENCE_IDENTIFIED: "Reference identified — not verified",
};

export default function Affordable8609AnnualPanel({
  propertyId, programId, buildingId, canEdit, onClose,
}: { propertyId: number; programId: number; buildingId: number; canEdit: boolean; onClose: () => void }) {
  const [taxYear, setTaxYear] = useState(new Date().getFullYear());
  const [rows, setRows] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<Category | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const path = `/api/properties/${propertyId}/affordable-programs/${programId}/buildings/${buildingId}/8609-annual`;

  useEffect(() => {
    let live = true;
    if (!Number.isInteger(taxYear) || taxYear < 1987 || taxYear > 2100) {
      setError("Choose a valid tax year."); setRows([]); setLoading(false);
      return () => { live = false; };
    }
    setRows([]); setLoading(true); setError(""); setMessage("");
    void (async () => {
      try {
        const result = await apiGet(`${path}?tax_year=${taxYear}`) as Item[];
        if (live) setRows(result);
      } catch {
        if (live) setError("Annual Form 8609-A staff references unavailable.");
      } finally { if (live) setLoading(false); }
    })();
    return () => { live = false; };
  }, [path, taxYear]);

  async function save(row: Item, status: Status) {
    setBusy(row.allocation_category); setError(""); setMessage("");
    try {
      const result = await apiPut(path, {
        tax_year: taxYear, allocation_category: row.allocation_category, status,
      }) as Item;
      setRows((prev) => prev.map((item) => item.allocation_category === result.allocation_category ? result : item));
      setMessage("Staff annual reference updated. No Form 8609-A was filed or tax credit calculated.");
    } catch {
      setError("Cannot update annual Form 8609-A reference.");
    } finally { setBusy(null); }
  }

  return (
    <section className="rounded border border-blue-200 bg-blue-50 p-4 text-sm" aria-label="Annual Form 8609-A reference index">
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-semibold">Annual Form 8609-A staff index · Building #{buildingId}</h4>
        <button type="button" onClick={onClose} className="rounded border px-2 py-1">Close</button>
      </div>
      <p className="mt-2">
        Record staff follow-up for a specific tax year. Acquisition/building and rehabilitation
        may require separate annual statements. These values are not evidence of an original
        agency-issued Form 8609, qualified basis, compliance-period completion, IRS filing,
        allowable credit, or recapture analysis. Do not enter tax IDs, income or credit amounts.
        Review{" "}
        <a href="https://www.irs.gov/instructions/i8609a" target="_blank"
          rel="noopener noreferrer" className="underline">IRS Form 8609-A instructions</a>.
      </p>
      <label className="mt-3 block max-w-40 text-xs">Tax year
        <input type="number" min={1987} max={2100} step={1}
          value={taxYear} onChange={(event) => setTaxYear(Number(event.target.value))}
          className="mt-1 w-full rounded border p-2" />
      </label>
      {loading && <p className="mt-2">Loading…</p>}
      {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
      {message && <p role="status" className="mt-2 text-green-800">{message}</p>}
      {!loading && <div className="mt-3 space-y-2">
        {rows.map((row) => (
          <label key={row.allocation_category} className="flex flex-wrap items-center justify-between gap-3 rounded border bg-white p-3">
            <span className="font-medium">{labels[row.allocation_category]}</span>
            <select value={row.status} disabled={!canEdit || busy !== null}
              onChange={(event) => { void save(row, event.target.value as Status); }}
              className="rounded border p-2">
              {Object.entries(choices).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </label>
        ))}
      </div>}
    </section>
  );
}
