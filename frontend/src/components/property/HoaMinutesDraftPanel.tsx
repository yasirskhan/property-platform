"use client";
import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Minutes = {
  id: number; meeting_draft_id: number; property_id: number;
  staff_minutes: string; revision: number; content_sha256: string;
  status: "STAFF_DRAFT_UNVERIFIED";
  legal_minutes_effective: false;
  board_approval_certified: false; quorum_certified: false;
};
type Approval = {
  id: number; minutes_revision: number; content_sha256: string;
  board_seat_id: number; approved_by_user_id: number; approved_at: string;
  approval_note: string; status: "BOARD_MEMBER_APPROVED";
  quorum_certified: false; full_board_vote_certified: false;
};

export default function HoaMinutesDraftPanel({
  associationId, propertyId, meetingId, canEdit,
}: {
  associationId: number; propertyId: number; meetingId: number; canEdit: boolean;
}) {
  const base = "/api/hoa/associations/" + associationId +
    "/meeting-drafts/" + meetingId + "/minutes-draft";
  const [record, setRecord] = useState<Minutes | null>(null);
  const [body, setBody] = useState("");
  const [boardPreview, setBoardPreview] = useState<Minutes | null>(null);
  const [approval, setApproval] = useState<Approval | null>(null);
  const [approvalNote, setApprovalNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(""); setMessage(""); setBody(""); setRecord(null);
    void (apiGet(base + "?property_id=" + propertyId) as Promise<Minutes | null>)
      .then((row) => { if (active) { setRecord(row); setBody(row?.staff_minutes || ""); } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Minutes unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, propertyId]);

  const loadBoard = useCallback(async () => {
    try {
      const [preview, existing] = await Promise.all([
        apiGet(base.replace("/minutes-draft", "/minutes-board-preview") + "?property_id=" + propertyId) as Promise<Minutes | null>,
        apiGet(base.replace("/minutes-draft", "/minutes-board-approval") + "?property_id=" + propertyId) as Promise<Approval | null>,
      ]);
      setBoardPreview(preview); setApproval(existing);
    } catch {
      // Staff without an authorized association board seat may still edit
      // staff drafts, but must not receive board-only approval data.
      setBoardPreview(null); setApproval(null);
    }
  }, [base, propertyId]);

  useEffect(() => {
    if (canEdit) void loadBoard();
    // Review controls re-evaluate when the selected meeting changes.
  }, [canEdit, loadBoard]);

  async function approve() {
    if (!boardPreview || !approvalNote.trim() || approval || busy || !canEdit) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await apiPost(base.replace("/minutes-draft", "/minutes-board-approval"), {
        property_id: propertyId, minutes_revision: boardPreview.revision,
        content_sha256: boardPreview.content_sha256, approval_note: approvalNote.trim(),
      }) as Approval;
      setApproval(saved);
      setMessage("Your authorized board-member approval was recorded for this exact minutes revision.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Minutes approval was not recorded.");
    } finally { setBusy(false); }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !body.trim() || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const row = await apiPut(base, {
        property_id: propertyId, staff_minutes: body.trim(),
      }) as Minutes;
      setRecord(row); setBody(row.staff_minutes);
      setBoardPreview(null); setApproval(null); setApprovalNote("");
      await loadBoard();
      setMessage("Staff minutes saved. No legal certification or vote was issued.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save minutes.");
    } finally { setBusy(false); }
  }

  async function archive() {
    if (!canEdit || !record || busy || !window.confirm(
      "Archive these staff minutes? The meeting will remain available."
    )) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "?property_id=" + propertyId);
      setRecord(null); setBody("");
      setMessage("Staff minutes archived. No official board action occurred.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive minutes.");
    } finally { setBusy(false); }
  }

  return (
    <section className="w-full space-y-2 rounded border border-amber-300 bg-white p-3 text-sm">
      <h5 className="font-semibold">Staff meeting minutes draft</h5>
      <p className="text-xs text-amber-900">
        Unverified internal notes only. Attendance, ballots and the minutes text
        do not establish legal quorum, adoption, approval or a board resolution.
        Certified minutes and document sharing require separate authority checks.
      </p>
      {loading && <p className="text-xs">Loading staff minutes…</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-green-700">{message}</p>}
      {approval && <p role="status" className="text-xs font-semibold text-teal-800">
        Board-member minutes approval recorded · Revision {approval.minutes_revision}
        {" · "}Approved by user #{approval.approved_by_user_id}. No full-board quorum is certified.
      </p>}
      {record && <p className="text-xs text-slate-600">
        {record.status.replaceAll("_", " ")} · Legal minutes effective: NO
      </p>}
      {!loading && canEdit && boardPreview && !approval && record && <div className="space-y-2 border-t pt-2">
        <p className="text-xs">Board approval applies only to revision {boardPreview.revision}.
          It records your decision, not certification of an entire board vote or quorum.</p>
        <label className="block text-xs">Board approval note
          <textarea aria-label="Board minutes approval note" maxLength={1500}
            value={approvalNote} onChange={event => setApprovalNote(event.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <button type="button" disabled={busy || !approvalNote.trim() || body.trim() !== record.staff_minutes}
          onClick={() => { void approve(); }}
          className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
          Approve this minutes revision as authorized board member
        </button>
      </div>}
      {!loading && canEdit && !approval ? (
        <form onSubmit={(event) => { void save(event); }} className="space-y-2">
          <label className="block text-xs">Staff minutes (not certified)
            <textarea value={body} maxLength={4000} required rows={5}
              onChange={(event) => setBody(event.target.value)}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <div className="flex gap-3">
            <button type="submit" disabled={busy || !body.trim()}
              className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
              Save staff minutes
            </button>
            {record && <button type="button" disabled={busy}
              onClick={() => { void archive(); }}
              className="rounded border px-3 py-2 text-red-700 disabled:opacity-50">
              Archive draft
            </button>}
          </div>
        </form>
      ) : <p className="whitespace-pre-wrap break-words">{record?.staff_minutes || "No staff minutes recorded."}</p>}
    </section>
  );
}
