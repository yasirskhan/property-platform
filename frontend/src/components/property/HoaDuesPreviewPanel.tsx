"use client";

import { useState } from "react";
import { apiGet } from "@/lib/api";

type Preview = {
  proposal_id: number;
  property_id: number;
  status: "UNISSUED_PREVIEW";
  issuance_enabled: false;
  frequency: string;
  proposed_total: string;
  occurrences: {
    proposed_on: string;
    proposed_amount: string;
    status: "DRAFT_ONLY";
  }[];
};

export default function HoaDuesPreviewPanel({
  associationId, propertyId, proposalId,
}: {
  associationId: number;
  propertyId: number;
  proposalId: number;
}) {
  const [from, setFrom] = useState("");
  const [through, setThrough] = useState("");
  const [data, setData] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function preview() {
    if (!from || !through || busy) return;
    setBusy(true); setError(""); setData(null);
    try {
      const qs = new URLSearchParams({
        property_id: String(propertyId), date_from: from, date_to: through,
      });
      const result = await apiGet(
        "/api/hoa/associations/" + associationId +
        "/draft-assessments/" + proposalId + "/preview?" + qs.toString()
      ) as Preview;
      setData(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preview unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full space-y-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
      <p className="text-xs text-amber-900">
        Calendar preview only. These are proposed planning dates, NOT HOA
        due dates. No payer, bill, fine, invoice, notice, or ledger entry
        is created. Governing authority and assessment rules are unverified.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <label>From
          <input type="date" value={from}
            onChange={(event) => { setFrom(event.target.value); setData(null); }}
            className="mt-1 block rounded border bg-white p-2" />
        </label>
        <label>Through
          <input type="date" value={through}
            onChange={(event) => { setThrough(event.target.value); setData(null); }}
            className="mt-1 block rounded border bg-white p-2" />
        </label>
        <button type="button" disabled={!from || !through || busy}
          onClick={() => { void preview(); }}
          className="rounded border bg-white px-3 py-2 disabled:opacity-50">
          {busy ? "Calculating…" : "Preview proposed dates"}
        </button>
      </div>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {data && (
        <div className="space-y-2">
          <p role="status" className="font-semibold">
            {data.occurrences.length} unissued planning dates · Proposed total ${data.proposed_total}
          </p>
          <ol className="list-inside list-decimal text-sm">
            {data.occurrences.map((row) => (
              <li key={row.proposed_on}>
                {row.proposed_on} · Proposed ${row.proposed_amount} · DRAFT ONLY
              </li>
            ))}
          </ol>
          <p className="text-xs text-amber-900">
            Not issued. The total is a mathematical preview, not receivables or payable funds.
          </p>
        </div>
      )}
    </div>
  );
}
