"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Adoption = {
  id: number; board_seat_id: number; quorum_min: number;
  approval_min: number; proposal_sha256: string; adopted_at: string;
};
type RuleRegister = {
  proposed_quorum_min: number | null;
  proposed_approval_min: number | null;
  proposal_sha256: string | null; active_adoption_id: number | null;
  history: Adoption[];
};

export default function HoaBoardRuleAdoptionPanel({
  associationId, propertyId,
}: { associationId: number; propertyId: number }) {
  const [register, setRegister] = useState<RuleRegister | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = "/api/hoa/associations/" + associationId + "/board-rule-adoptions";
  const query = "?property_id=" + propertyId;

  useEffect(() => {
    let live = true;
    void (apiGet(base + query) as Promise<RuleRegister>)
      .then(rows => { if (live) setRegister(rows); })
      .catch(cause => { if (live) setError(cause instanceof Error ? cause.message : "Board rules unavailable."); });
    return () => { live = false; };
  }, [base, query]);

  async function adopt() {
    if (busy || !register?.proposal_sha256 || register.active_adoption_id !== null) return;
    if (!window.confirm("Record your association board adoption of these exact configured voting thresholds?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId,
        expected_proposal_sha256: register.proposal_sha256,
      });
      setRegister(await apiGet(base + query) as RuleRegister);
      setMessage("Board member adoption recorded on the exact configured revision.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to adopt this rule revision.");
    } finally { setBusy(false); }
  }

  return <div className="space-y-2 rounded border bg-slate-50 p-3 text-xs">
    <h3 className="font-semibold">Association voting thresholds</h3>
    <p>The association configures the quorum and approval numbers. An authorized
      board member adopts the exact configured revision. This does not certify
      applicable law or automatically decide any motion.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-teal-800">{message}</p>}
    {!register && !error && <p>Loading association thresholds…</p>}
    {register && <>
      {register.proposal_sha256 ? <>
        <p>Configured quorum: {register.proposed_quorum_min} · Approval threshold: {register.proposed_approval_min}</p>
        {register.active_adoption_id !== null ?
          <p role="status">Association board adoption recorded for this revision.</p> :
          <button type="button" disabled={busy} onClick={() => { void adopt(); }}
            className="rounded border border-teal-800 p-2 text-teal-900 disabled:opacity-50">
            Adopt configured board thresholds
          </button>}
      </> : <p>No complete quorum and approval configuration. Organization staff must enter both numbers first.</p>}
      {register.history.length > 0 && <details>
        <summary>Historical board threshold adoptions</summary>
        <ol className="space-y-1">
          {register.history.map(row => <li key={row.id}>
            Board seat #{row.board_seat_id} · Quorum {row.quorum_min} ·
            Approval {row.approval_min} · Recorded {row.adopted_at}
          </li>)}
        </ol>
      </details>}
    </>}
  </div>;
}
