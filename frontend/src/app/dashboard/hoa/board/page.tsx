"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Meeting = {
  association_id: number; property_id: number; meeting_id: number;
  title: string; proposed_on: string; staff_agenda: string | null;
};
type Minutes = {
  id: number; staff_minutes: string; revision: number; content_sha256: string;
};
type Approval = {
  id: number; minutes_revision: number; board_seat_id: number;
  approved_by_user_id: number; approved_at: string; approval_note: string;
  status: "BOARD_MEMBER_APPROVED"; quorum_certified: false;
};
type Detail = { minutes: Minutes | null; approval: Approval | null };

function url(meeting: Meeting) {
  return "/api/hoa/associations/" + meeting.association_id +
    "/meeting-drafts/" + meeting.meeting_id;
}

export default function HOABoardPortal() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, Detail>>({});
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    void (apiGet("/api/hoa/board/my-meetings") as Promise<Meeting[]>)
      .then(rows => { if (live) setMeetings(rows); })
      .catch(cause => {
        if (live) setError(cause instanceof Error ? cause.message : "Board workspace unavailable.");
      }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  async function view(meeting: Meeting) {
    if (busy) return;
    if (selected === meeting.meeting_id) { setSelected(null); return; }
    setBusy(true); setError(""); setMessage(""); setNote("");
    try {
      const suffix = "?property_id=" + meeting.property_id;
      const [minutes, approval] = await Promise.all([
        apiGet(url(meeting) + "/minutes-board-preview" + suffix) as Promise<Minutes | null>,
        apiGet(url(meeting) + "/minutes-board-approval" + suffix) as Promise<Approval | null>,
      ]);
      setDetails(prior => ({ ...prior, [meeting.meeting_id]: { minutes, approval } }));
      setSelected(meeting.meeting_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Minutes unavailable.");
    } finally { setBusy(false); }
  }

  async function approve(meeting: Meeting) {
    const minutes = details[meeting.meeting_id]?.minutes;
    if (!minutes || busy || !note.trim() || details[meeting.meeting_id]?.approval) return;
    if (!window.confirm("Record your board-member approval of this exact minutes revision?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await apiPost(url(meeting) + "/minutes-board-approval", {
        property_id: meeting.property_id,
        minutes_revision: minutes.revision,
        content_sha256: minutes.content_sha256,
        approval_note: note.trim(),
      }) as Approval;
      setDetails(prior => ({
        ...prior,
        [meeting.meeting_id]: { minutes, approval: saved },
      }));
      setNote("");
      setMessage("Your board-member approval of this minutes revision was recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Approval was not recorded. Reload the minutes.");
    } finally { setBusy(false); }
  }

  return <section className="max-w-4xl space-y-4">
    <h1 className="text-2xl font-semibold">My HOA board meetings</h1>
    <p className="text-sm text-slate-600">
      Only meetings for your currently authorized association-specific board seat appear.
      Approving minutes records your individual decision. This is not certification of
      quorum, a full-board vote, statutory delivery, or any financial transaction.
    </p>
    {loading && <p>Loading authorized meetings…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {!loading && meetings.length === 0 && !error &&
      <p>No meetings are available to your authorized board account.</p>}
    {meetings.map(meeting => {
      const detail = details[meeting.meeting_id];
      const isOpen = selected === meeting.meeting_id;
      return <article key={meeting.meeting_id} className="space-y-3 rounded border bg-white p-4">
        <h2 className="font-medium">{meeting.title}</h2>
        <p className="text-xs text-slate-600">
          Association #{meeting.association_id} · Property #{meeting.property_id}
          {" · "}Meeting {meeting.proposed_on}
        </p>
        {meeting.staff_agenda && <p className="whitespace-pre-wrap text-sm">
          Agenda: {meeting.staff_agenda}</p>}
        <button type="button" disabled={busy} onClick={() => { void view(meeting); }}
          className="text-blue-700 disabled:opacity-50">
          {isOpen ? "Close board minutes" : "Review board minutes"}
        </button>
        {isOpen && detail && <div className="space-y-3 border-t pt-3">
          {detail.minutes ? <>
            <h3 className="font-medium">Recorded minutes, revision {detail.minutes.revision}</h3>
            <p className="whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-sm">
              {detail.minutes.staff_minutes}</p>
            {detail.approval ? <p role="status" className="text-sm text-teal-800">
              BOARD MEMBER APPROVED · Revision {detail.approval.minutes_revision}
              {" · "}Recorded {detail.approval.approved_at}.
              This is not a certified full-board quorum.
            </p> : <div className="space-y-2">
              <label className="block text-sm">Board approval note
                <textarea aria-label="Portal board approval note" value={note}
                  onChange={event => setNote(event.target.value)} maxLength={1500}
                  className="mt-1 block w-full rounded border p-2" />
              </label>
              <button type="button" disabled={busy || note.trim().length < 3}
                onClick={() => { void approve(meeting); }}
                className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
                Approve exact minutes revision
              </button>
            </div>}
          </> : <p>No active staff minutes have been recorded for this meeting.</p>}
        </div>}
      </article>;
    })}
  </section>;
}
