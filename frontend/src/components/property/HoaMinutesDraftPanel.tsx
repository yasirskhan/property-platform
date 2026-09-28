"use client";
import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPut } from "@/lib/api";

type Minutes = {
  id: number; meeting_draft_id: number; property_id: number;
  staff_minutes: string; status: "STAFF_DRAFT_UNVERIFIED";
  legal_minutes_effective: false;
  board_approval_certified: false; quorum_certified: false;
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    setError(""); setMessage(""); setBody(""); setRecord(null);
    void (apiGet(base + "?property_id=" + propertyId) as Promise<Minutes | null>)
      .then((row) => { if (active) { setRecord(row); setBody(row?.staff_minutes || ""); } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Minutes unavailable."); });
    return () => { active = false; };
  }, [base, propertyId]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !body.trim() || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const row = await apiPut(base, {
        property_id: propertyId, staff_minutes: body.trim(),
      }) as Minutes;
      setRecord(row); setBody(row.staff_minutes);
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
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-green-700">{message}</p>}
      {record && <p className="text-xs text-slate-600">
        {record.status.replaceAll("_", " ")} · Legal minutes effective: NO
      </p>}
      {canEdit ? (
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
