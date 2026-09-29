"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Recorded = {
  id: number; motion_draft_id: number; outcome: "PASSED" | "NOT_PASSED";
  votes_for: number; votes_against: number; votes_abstain: number;
  quorum_min: number; approval_min: number; recorded_at: string;
};
type Preview = {
  motion_sha256: string;
  rule_adoption_id: number | null; vote_register_sha256: string;
  quorum_min: number | null; approval_min: number | null;
  votes_for: number; votes_against: number; votes_abstain: number;
  quorum_met: boolean; predicted_outcome: "PASSED" | "NOT_PASSED" | null;
  recorded: Recorded | null;
};

export default function HoaBoardMotionOutcomePanel({
  associationId, propertyId, meetingId, motionId, voteCount,
}: {
  associationId: number; propertyId: number; meetingId: number;
  motionId: number; voteCount: number;
}) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const base = "/api/hoa/associations/" + associationId +
    "/meeting-drafts/" + meetingId + "/board-motions/" + motionId + "/outcome";
  const query = "?property_id=" + propertyId;

  useEffect(() => {
    let live = true;
    void (apiGet(base + query) as Promise<Preview>)
      .then(value => { if (live) setPreview(value); })
      .catch(cause => { if (live) setError(cause instanceof Error ? cause.message : "Motion tally unavailable."); });
    return () => { live = false; };
  }, [base, query, voteCount]);

  async function finalize() {
    if (!preview || busy || preview.recorded || !preview.quorum_met ||
        preview.rule_adoption_id === null) return;
    if (!window.confirm("Close the recorded vote and record the board's final motion outcome under the adopted thresholds?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId,
        motion_sha256: preview.motion_sha256,
        rule_adoption_id: preview.rule_adoption_id,
        expected_vote_register_sha256: preview.vote_register_sha256,
      });
      setPreview(await apiGet(base + query) as Preview);
      setMessage("Final association board motion outcome recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Final tally not recorded. Review current votes and rules.");
    } finally { setBusy(false); }
  }

  return <div className="space-y-1 rounded border bg-slate-50 p-2 text-xs">
    <h4 className="font-semibold">Final board motion outcome</h4>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-teal-800">{message}</p>}
    {!preview && !error && <p>Loading final tally…</p>}
    {preview && <>
      <p>Recorded: {preview.votes_for} FOR · {preview.votes_against} AGAINST ·
        {" "}{preview.votes_abstain} ABSTAIN.</p>
      {preview.recorded ? <p role="status" className="font-medium text-teal-900">
        Board motion outcome: {preview.recorded.outcome}. Recorded {preview.recorded.recorded_at}.
        {" "}Quorum {preview.recorded.quorum_min} · Approval {preview.recorded.approval_min}.
        Voting closed. This records the association's decision, not a legal opinion.
      </p> : preview.rule_adoption_id === null ?
        <p>The association must adopt its configured quorum and approval thresholds first.</p> :
        !preview.quorum_met ?
          <p>Recorded votes have not met the adopted quorum of {preview.quorum_min}.</p> :
          <div className="space-y-1">
            <p>Under adopted quorum {preview.quorum_min} and approval threshold {preview.approval_min},
              the recorded tally is {preview.predicted_outcome}. A board member must confirm finalization.</p>
            <button type="button" disabled={busy} onClick={() => { void finalize(); }}
              className="rounded border border-teal-800 px-3 py-2 text-teal-900 disabled:opacity-50">
              Record final board motion outcome
            </button>
          </div>}
      <p>No statutory compliance certification, notice or financial posting is made by this screen.</p>
    </>}
  </div>;
}
