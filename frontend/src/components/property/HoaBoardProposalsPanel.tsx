"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Link = { id: number; contact_name: string };
type Seat = { id: number; contact_link_id: number; contact_name: string;
  proposed_role: string; staff_voting_eligible: boolean; vote_enabled: false };
type Rules = { id: number; proposed_quorum_min: number | null;
  proposed_approval_min: number | null; vote_enabled: false };
type Board = { seats: Seat[]; rules: Rules | null;
  vote_enabled: false; authority_verified: false };
const roles = ["CHAIR", "VICE_CHAIR", "SECRETARY", "TREASURER", "DIRECTOR", "ALTERNATE"];

export default function HoaBoardProposalsPanel({
  associationId, propertyId, canEdit, onClose,
}: { associationId: number; propertyId: number; canEdit: boolean; onClose: () => void }) {
  const [board, setBoard] = useState<Board | null>(null);
  const [links, setLinks] = useState<Link[]>([]);
  const [contactLinkId, setContactLinkId] = useState("");
  const [role, setRole] = useState("DIRECTOR");
  const [eligible, setEligible] = useState(false);
  const [quorum, setQuorum] = useState("");
  const [approval, setApproval] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = "/api/hoa/associations/" + associationId;
  const suffix = "?property_id=" + propertyId;

  useEffect(() => {
    let live = true;
    setBoard(null); setError("");
    void Promise.all([
      apiGet(base + "/board-proposals" + suffix) as Promise<Board>,
      apiGet(base + "/contacts" + suffix) as Promise<Link[]>,
    ]).then(([roster, contacts]) => {
      if (!live) return;
      setBoard(roster); setLinks(contacts);
      setQuorum(roster.rules?.proposed_quorum_min?.toString() || "");
      setApproval(roster.rules?.proposed_approval_min?.toString() || "");
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Board proposals unavailable.");
    });
    return () => { live = false; };
  }, [base, suffix]);

  async function refresh() {
    const next = await apiGet(base + "/board-proposals" + suffix) as Board;
    setBoard(next);
  }

  async function record(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !contactLinkId || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/board-proposals/seats", {
        property_id: propertyId, contact_link_id: Number(contactLinkId),
        proposed_role: role, staff_voting_eligible: eligible,
      });
      setContactLinkId(""); setEligible(false);
      await refresh();
      setMessage("Staff-proposed board contact recorded. Voting remains disabled.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record seat proposal.");
    } finally { setBusy(false); }
  }

  async function saveRules(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPut(base + "/board-proposals/rules", {
        property_id: propertyId,
        proposed_quorum_min: quorum ? Number(quorum) : null,
        proposed_approval_min: approval ? Number(approval) : null,
      });
      await refresh();
      setMessage("Proposed thresholds saved; no quorum or vote is certified.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record thresholds.");
    } finally { setBusy(false); }
  }

  async function archive(seat: Seat) {
    if (!canEdit || busy || !window.confirm("Archive this staff board contact proposal?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/board-proposals/seats/" + seat.id + suffix);
      await refresh();
      setMessage("Seat proposal archived. No governing action changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot archive seat.");
    } finally { setBusy(false); }
  }

  const available = links.filter(link => !board?.seats.some(seat => seat.contact_link_id === link.id));
  return (
    <section className="w-full space-y-3 rounded-lg border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Board role and voting rule proposals</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-600">
        Staff-entered contact roles and proposed thresholds are NOT authenticated board
        membership, voting eligibility, quorum, approval or a legally effective decision.
        Board-member sign-in and formal votes are not enabled.
      </p>
      {error && <p role="alert" className="text-red-700 text-sm">{error}</p>}
      {message && <p role="status" className="text-green-700 text-sm">{message}</p>}
      {!board && !error && <p className="text-sm">Loading board proposals…</p>}
      {board && <>
        {board.seats.length === 0 && <p className="text-sm">No staff board contact proposals.</p>}
        {board.seats.map(seat => (
          <div key={seat.id} className="flex items-center justify-between gap-2 rounded border bg-white p-2 text-sm">
            <div>{seat.contact_name}: {seat.proposed_role} · Staff-proposed eligible: {seat.staff_voting_eligible ? "Yes" : "No"}
              <p className="text-xs text-amber-800">Unverified. Vote disabled.</p>
            </div>
            {canEdit && <button type="button" disabled={busy} onClick={() => { void archive(seat); }}
              className="text-red-700 disabled:opacity-50">Archive</button>}
          </div>
        ))}
        <p className="text-xs text-slate-600">
          Proposed quorum: {board.rules?.proposed_quorum_min ?? "Not set"} ·
          Proposed approval threshold: {board.rules?.proposed_approval_min ?? "Not set"} ·
          No verified board authority.
        </p>
        {canEdit && <>
          <form onSubmit={(event) => { void record(event); }} className="space-y-2 border-t pt-2">
            <label className="block text-sm">Existing scoped HOA contact
              <select value={contactLinkId} required onChange={event => setContactLinkId(event.target.value)}
                className="mt-1 block w-full rounded border p-2">
                <option value="">Select contact</option>
                {available.map(link => <option key={link.id} value={link.id}>{link.contact_name}</option>)}
              </select>
            </label>
            <label className="block text-sm">Proposed role
              <select value={role} onChange={event => setRole(event.target.value)}
                className="mt-1 block w-full rounded border p-2">
                {roles.map(r => <option key={r} value={r}>{r.replaceAll("_", " ")}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={eligible} onChange={event => setEligible(event.target.checked)} />
              Staff-proposed voting eligibility (does not authorize a vote)
            </label>
            <button type="submit" disabled={busy || !contactLinkId}
              className="rounded border bg-white px-3 py-2 disabled:opacity-50">Record role proposal</button>
          </form>
          <form onSubmit={(event) => { void saveRules(event); }} className="space-y-2 border-t pt-2">
            <div className="flex flex-wrap gap-3">
              <label className="text-sm">Proposed minimum quorum
                <input type="number" min={1} max={500} value={quorum}
                  onChange={event => setQuorum(event.target.value)}
                  className="mt-1 block rounded border p-2" />
              </label>
              <label className="text-sm">Proposed approval threshold
                <input type="number" min={1} max={500} value={approval}
                  onChange={event => setApproval(event.target.value)}
                  className="mt-1 block rounded border p-2" />
              </label>
            </div>
            <button type="submit" disabled={busy}
              className="rounded border bg-white px-3 py-2 disabled:opacity-50">Save proposed rules</button>
          </form>
        </>}
      </>}
    </section>
  );
}
