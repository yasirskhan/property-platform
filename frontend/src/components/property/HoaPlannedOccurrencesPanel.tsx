"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Occurrence = {
  id: number;
  proposed_on: string;
  proposed_amount: string;
  payer_draft_id: number;
  status: "PLANNED" | "VOIDED";
  is_issued: boolean;
  is_receivable: boolean;
  gl_posting_enabled: boolean;
};
type Readiness = { status: string; posting_enabled: false; reversal_enabled: false;
  missing_requirements: string[]; accounting_period_unlocked: boolean };
type Generation = {
  new_count: number;
  existing_count: number;
  rows: Occurrence[];
  status: "PLANNING_ONLY";
};

export default function HoaPlannedOccurrencesPanel({
  associationId, propertyId, proposalId, canEdit,
}: {
  associationId: number;
  propertyId: number;
  proposalId: number;
  canEdit: boolean;
}) {
  const [rows, setRows] = useState<Occurrence[]>([]);
  const [readiness, setReadiness] = useState<Record<number, Readiness>>({});
  const [from, setFrom] = useState("");
  const [through, setThrough] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = "/api/hoa/associations/" + associationId +
    "/draft-assessments/" + proposalId + "/planned-occurrences";
  const query = "?property_id=" + propertyId;

  useEffect(() => {
    let active = true;
    setLoading(true); setRows([]); setError("");
    void (apiGet(base + query) as Promise<Occurrence[]>).then((data) => {
      if (active) setRows(data);
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "History unavailable.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, query]);

  async function reload() {
    const found = await apiGet(base + query) as Occurrence[];
    setRows(found);
  }

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !from || !through || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost(base + "/generate", {
        property_id: propertyId, date_from: from, date_to: through,
      }) as Generation;
      await reload();
      setMessage(result.new_count + " new planning periods; " +
        result.existing_count + " existing periods unchanged. Nothing issued or posted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record planning periods.");
    } finally { setBusy(false); }
  }

  async function checkReadiness(row: Occurrence) {
    setBusy(true); setError("");
    try {
      const result = await apiGet(base + "/" + row.id +
        "/issuance-readiness" + query) as Readiness;
      setReadiness((prior) => ({ ...prior, [row.id]: result }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Readiness unavailable.");
    } finally { setBusy(false); }
  }

  async function voidPlan(row: Occurrence) {
    if (!canEdit || busy || !window.confirm("Void this unissued planning period?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/void" + query, {});
      await reload();
      setMessage("Unissued planning period voided. This is not a financial reversal.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to void planning period.");
    } finally { setBusy(false); }
  }

  return <section className="w-full space-y-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
    <h4 className="font-semibold">Unissued assessment planning history</h4>
    <p className="text-xs text-amber-900">
      Requires a previously suggested contact, not a legally verified payer.
      These are durable schedule snapshots only. No legal due date, charge,
      invoice, payment obligation, reversal, or general ledger entry is created.
      A voided planning row cannot be silently regenerated.
    </p>
    {loading && <p>Loading planning history…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-700">{message}</p>}
    {!loading && rows.length === 0 && <p>No planning periods have been recorded.</p>}
    {!loading && rows.length > 0 && <ol className="space-y-1">
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-center gap-2">
        <span>{row.proposed_on} · Proposed ${row.proposed_amount} · {row.status}{row.is_issued ? " · ISSUED TO MEMBER" : ""}</span>
        {canEdit && !row.is_issued && <button type="button" disabled={busy}
          onClick={() => { void checkReadiness(row); }}
          className="text-blue-700 disabled:opacity-50">Posting readiness</button>}
        {readiness[row.id] && <p className="w-full text-xs text-amber-900" role="status">
          Posting and reversal DISABLED. Outstanding prerequisites: {
            readiness[row.id].missing_requirements.join(", ").replaceAll("_", " ").toLowerCase()
          }.
        </p>}
        {canEdit && row.status === "PLANNED" && !row.is_issued &&
          <button type="button" disabled={busy} onClick={() => { void voidPlan(row); }}
            className="text-red-700 disabled:opacity-50">Void draft</button>}
      </li>)}
    </ol>}
    {canEdit && !loading && <form onSubmit={(event) => { void generate(event); }}
      className="flex flex-wrap items-end gap-2 border-t pt-2">
      <label>From<input type="date" required value={from} onChange={(e) => setFrom(e.target.value)}
        className="mt-1 block rounded border bg-white p-2" /></label>
      <label>Through<input type="date" required value={through} onChange={(e) => setThrough(e.target.value)}
        className="mt-1 block rounded border bg-white p-2" /></label>
      <button type="submit" disabled={!from || !through || busy}
        className="rounded border bg-white px-3 py-2 disabled:opacity-50">
        {busy ? "Recording…" : "Record unissued schedule"}
      </button>
    </form>}
  </section>;
}
