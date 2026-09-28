"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import HoaBallotRecordsPanel from "@/components/property/HoaBallotRecordsPanel";

type ContactLink = {
  id: number; contact_id: number; contact_name: string;
};
type Attendance = {
  id: number; contact_link_id: number; contact_name: string;
  staff_attendance: "PRESENT" | "ABSENT" | "UNCONFIRMED";
  status: "STAFF_REPORTED_UNVERIFIED";
};
type Motion = {
  id: number; proposed_motion: string; status: "PROPOSED_ONLY";
  vote_enabled: false;
};
type Workspace = {
  attendance: Attendance[]; motions: Motion[];
  board_authority_verified: false;
  quorum_certified: false;
  vote_enabled: false;
};

export default function HoaMeetingWorkspacePanel({
  associationId, propertyId, meetingId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; meetingId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId
    + "/meeting-drafts/" + meetingId + "/workspace";
  const query = "?property_id=" + propertyId;
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [contacts, setContacts] = useState<ContactLink[]>([]);
  const [linkId, setLinkId] = useState("");
  const [attendance, setAttendance] = useState<Attendance["staff_attendance"]>("UNCONFIRMED");
  const [motion, setMotion] = useState("");
  const [ballotMotionId, setBallotMotionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function reload() {
    const result = await apiGet(base + query) as Workspace;
    setWorkspace(result);
  }

  useEffect(() => {
    let live = true;
    setLoading(true); setError(""); setMessage("");
    void Promise.all([
      apiGet(base + query) as Promise<Workspace>,
      apiGet("/api/hoa/associations/" + associationId + "/contacts" + query) as Promise<ContactLink[]>,
    ]).then(([result, linked]) => {
      if (!live) return;
      setWorkspace(result);
      setContacts(linked);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Staff workspace unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [base, query, associationId]);

  async function recordAttendance(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !linkId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/attendance", {
        property_id: propertyId,
        contact_link_id: Number(linkId),
        staff_attendance: attendance,
      });
      await reload();
      setLinkId(""); setAttendance("UNCONFIRMED");
      setMessage("Unverified staff attendance recorded. This is not a board credential or quorum.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record attendance.");
    } finally { setBusy(false); }
  }

  async function proposeMotion(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !motion.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/motions", {
        property_id: propertyId, proposed_motion: motion.trim(),
      });
      await reload();
      setMotion("");
      setMessage("Staff motion draft saved. No vote has occurred.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record a proposed motion.");
    } finally { setBusy(false); }
  }

  async function archive(path: string, id: number) {
    if (!canEdit || busy || !window.confirm("Archive this unverified staff record?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + path + "/" + id + query);
      await reload();
      setMessage("Staff record archived. No legal board decision was affected.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive staff record.");
    } finally { setBusy(false); }
  }

  return (
    <section className="w-full space-y-3 rounded border bg-amber-50 p-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">Staff meeting participation and motion preparation</h4>
        <button type="button" onClick={onClose} className="text-blue-700">Close workspace</button>
      </div>
      <p className="text-xs text-amber-900">
        Contact links are staff references, not verified board seats. Attendance is staff-reported.
        Motions are proposals, not official votes, resolutions or certified quorum. No board member
        login, legal eligibility or approval is established here. Meeting minutes can be stored
        privately through the existing governing-evidence documents panel.
      </p>
      {loading && <p className="text-xs">Loading staff meeting records…</p>}
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      {message && <p role="status" className="text-xs text-green-700">{message}</p>}
      {workspace && !loading && (
        <>
          <h5 className="text-sm font-semibold">Staff-reported participation</h5>
          {workspace.attendance.length === 0 && (
            <p className="text-xs text-slate-600">No staff attendance recorded.</p>
          )}
          {workspace.attendance.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded border bg-white p-2 text-sm">
              <span>{row.contact_name} · {row.staff_attendance} · UNVERIFIED</span>
              {canEdit && (
                <button type="button" disabled={busy} onClick={() => { void archive("/attendance", row.id); }}
                  className="text-red-700 disabled:opacity-50">Archive attendance</button>
              )}
            </div>
          ))}
          {canEdit && contacts.length > 0 && (
            <form onSubmit={(event) => { void recordAttendance(event); }} className="flex flex-wrap items-end gap-2">
              <label className="text-xs">Staff contact reference
                <select required value={linkId} onChange={(event) => setLinkId(event.target.value)}
                  className="mt-1 block rounded border bg-white p-2">
                  <option value="">Choose an association contact</option>
                  {contacts.map((row) => (
                    <option key={row.id} value={row.id}>{row.contact_name}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs">Staff-reported attendance
                <select value={attendance}
                  onChange={(event) => setAttendance(event.target.value as Attendance["staff_attendance"])}
                  className="mt-1 block rounded border bg-white p-2">
                  <option value="UNCONFIRMED">Unconfirmed</option>
                  <option value="PRESENT">Reported present</option>
                  <option value="ABSENT">Reported absent</option>
                </select>
              </label>
              <button type="submit" disabled={busy || !linkId}
                className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">Record staff attendance</button>
            </form>
          )}
          <h5 className="text-sm font-semibold">Proposed motions (no votes)</h5>
          {workspace.motions.length === 0 && (
            <p className="text-xs text-slate-600">No staff motion proposals.</p>
          )}
          {workspace.motions.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded border bg-white p-2 text-sm">
              <span>{row.proposed_motion} · PROPOSED ONLY</span>
              <button type="button" onClick={() => setBallotMotionId(
                (old) => old === row.id ? null : row.id
              )} className="text-blue-700">Staff ballot records</button>
              {canEdit && (
                <button type="button" disabled={busy} onClick={() => { void archive("/motions", row.id); }}
                  className="text-red-700 disabled:opacity-50">Archive motion draft</button>
              )}
              {ballotMotionId === row.id && (
                <HoaBallotRecordsPanel associationId={associationId} propertyId={propertyId}
                  meetingId={meetingId} motionId={row.id} canEdit={canEdit} />
              )}
            </div>
          ))}
          {canEdit && (
            <form onSubmit={(event) => { void proposeMotion(event); }} className="space-y-2">
              <label className="block text-xs">Proposed staff motion
                <textarea value={motion} required maxLength={1000}
                  onChange={(event) => setMotion(event.target.value)}
                  className="mt-1 block w-full rounded border bg-white p-2" />
              </label>
              <button type="submit" disabled={busy || !motion.trim()}
                className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">Save motion draft</button>
            </form>
          )}
        </>
      )}
    </section>
  );
}
