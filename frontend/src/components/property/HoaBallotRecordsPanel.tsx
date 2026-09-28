"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";

type BoardSeat = {
  id: number;
  contact_name: string;
  proposed_role: string;
  staff_voting_eligible: boolean;
};
type Board = { seats: BoardSeat[]; vote_enabled: false };
type Report = {
  id: number;
  board_seat_id: number;
  contact_name: string;
  staff_reported_choice: "FOR" | "AGAINST" | "ABSTAIN";
  vote_effective: false;
};
type Ballots = {
  ballots: Report[];
  vote_effective: false;
  quorum_certified: false;
  approval_certified: false;
};

export default function HoaBallotRecordsPanel({
  associationId, propertyId, meetingId, motionId, canEdit,
}: {
  associationId: number; propertyId: number;
  meetingId: number; motionId: number; canEdit: boolean;
}) {
  const [board, setBoard] = useState<Board | null>(null);
  const [result, setResult] = useState<Ballots | null>(null);
  const [seat, setSeat] = useState("");
  const [choice, setChoice] = useState<Report["staff_reported_choice"]>("ABSTAIN");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const base = "/api/hoa/associations/" + associationId;
  const route = base + "/meeting-drafts/" + meetingId + "/motions/" + motionId + "/ballot-records";
  const qs = "?property_id=" + propertyId;

  async function reload() {
    const [people, reports] = await Promise.all([
      apiGet(base + "/board-proposals" + qs) as Promise<Board>,
      apiGet(route + qs) as Promise<Ballots>,
    ]);
    setBoard(people); setResult(reports);
  }
  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base + "/board-proposals" + qs) as Promise<Board>,
      apiGet(route + qs) as Promise<Ballots>,
    ]).then(([people, reports]) => {
      if (live) { setBoard(people); setResult(reports); }
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Staff ballot records unavailable.");
    });
    return () => { live = false; };
  }, [base, qs, route]);

  async function record(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !seat || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(route, {
        property_id: propertyId,
        board_seat_id: Number(seat),
        staff_reported_choice: choice,
      });
      setSeat(""); await reload();
      setMessage("Staff-reported choice recorded. No legally effective vote occurred.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record staff choice.");
    } finally { setBusy(false); }
  }

  async function archive(row: Report) {
    if (!canEdit || busy || !window.confirm("Archive this staff ballot report?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(route + "/" + row.id + qs);
      await reload();
      setMessage("Staff report archived; no board resolution was changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive staff report.");
    } finally { setBusy(false); }
  }

  const options = board?.seats.filter(person => (
    person.staff_voting_eligible &&
    !result?.ballots.some(row => row.board_seat_id === person.id)
  )) || [];
  return (
    <div className="w-full space-y-2 rounded border border-amber-300 bg-white p-3 text-xs">
      <h5 className="font-semibold">Staff-reported ballot observations</h5>
      <p className="text-amber-900">
        This records an unverified staff observation, NOT a ballot cast by an
        authenticated board member. No official vote, quorum, passage,
        resolution or legal approval is computed or recorded.
      </p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-green-700">{message}</p>}
      {result?.ballots.length === 0 && <p>No reported ballot observations.</p>}
      {result?.ballots.map(row => (
        <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 border-t pt-2">
          <span>{row.contact_name} · {row.staff_reported_choice} · UNVERIFIED</span>
          {canEdit && <button type="button" disabled={busy}
            onClick={() => { void archive(row); }}
            className="text-red-700 disabled:opacity-50">Archive report</button>}
        </div>
      ))}
      {canEdit && (
        <form onSubmit={(event) => { void record(event); }} className="flex flex-wrap items-end gap-2 border-t pt-2">
          <label>Staff-proposed eligible contact
            <select value={seat} required onChange={event => setSeat(event.target.value)}
              className="mt-1 block rounded border p-2">
              <option value="">Choose proposed contact</option>
              {options.map(person => <option key={person.id} value={person.id}>
                {person.contact_name} ({person.proposed_role})
              </option>)}
            </select>
          </label>
          <label>Staff-reported choice
            <select value={choice} onChange={event => setChoice(
              event.target.value as Report["staff_reported_choice"]
            )} className="mt-1 block rounded border p-2">
              <option value="ABSTAIN">Abstain</option>
              <option value="FOR">For</option>
              <option value="AGAINST">Against</option>
            </select>
          </label>
          <button type="submit" disabled={busy || !seat}
            className="rounded border px-3 py-2 disabled:opacity-50">
            Record staff observation
          </button>
        </form>
      )}
    </div>
  );
}
