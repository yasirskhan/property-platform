"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Appeal = {
  association_id: number; property_id: number; case_id: number;
  fine_id: number; appeal_id: number; received_on: string;
  member_user_id: number; appeal_reason: string; status: "OPEN";
};

export default function HoaBoardFineAppealsPanel() {
  const [appeals, setAppeals] = useState<Appeal[]>([]);
  const [choices, setChoices] = useState<Record<number, "UPHELD" | "VACATED">>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKeys = useRef<Record<number, string>>({});

  async function reload() {
    setAppeals(await apiGet("/api/hoa/board/my-fine-appeals") as Appeal[]);
  }

  useEffect(() => {
    let live = true;
    void apiGet("/api/hoa/board/my-fine-appeals").then(rows => {
      if (live) setAppeals(rows as Appeal[]);
    }).catch(cause => {
      if (live) setError(cause instanceof Error ? cause.message : "Board appeals unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  async function decide(appeal: Appeal) {
    if (busy || !(notes[appeal.appeal_id] || "").trim()) return;
    const choice = choices[appeal.appeal_id] || "UPHELD";
    if (!window.confirm("Record your association board " + choice +
      " appeal disposition? Existing member payments and GL entries are not automatically reversed.")) return;
    if (!requestKeys.current[appeal.appeal_id]) {
      requestKeys.current[appeal.appeal_id] = window.crypto.randomUUID();
    }
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost("/api/hoa/associations/" + appeal.association_id +
        "/staff-cases/" + appeal.case_id + "/fine/appeals/" +
        appeal.appeal_id + "/decision", {
        property_id: appeal.property_id, result: choice,
        decision_note: notes[appeal.appeal_id].trim(),
        request_key: requestKeys.current[appeal.appeal_id],
      });
      delete requestKeys.current[appeal.appeal_id];
      await reload();
      setMessage("Your direct board appeal disposition was recorded; separate accounting correction is required if vacated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Board disposition rejected.");
    } finally { setBusy(false); }
  }

  return <section className="space-y-3 rounded border bg-white p-4">
    <h2 className="font-semibold">Board fine appeals</h2>
    <p className="text-xs text-slate-600">
      Only open appeals within your verified association-specific board authority
      are shown. UPHELD/VACATED records the association decision, not a refund,
      mailed notice, or automatic change to previously posted GL entries.
    </p>
    {loading && <p className="text-xs">Loading board appeals…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {!loading && appeals.length === 0 && !error &&
      <p className="text-sm">No open appeals for your currently authorized board seats.</p>}
    {appeals.map(appeal => <article key={appeal.appeal_id}
      className="space-y-2 rounded border bg-slate-50 p-3 text-sm">
      <h3 className="font-medium">Fine appeal #{appeal.appeal_id}</h3>
      <p className="text-xs">Association #{appeal.association_id}
        {" · "}Property #{appeal.property_id} · Case #{appeal.case_id}
        {" · "}Member #{appeal.member_user_id}</p>
      <p>Received {appeal.received_on} · {appeal.status}</p>
      <p className="whitespace-pre-wrap break-words">Member appeal reason: {appeal.appeal_reason}</p>
      <label className="block text-sm">Board appeal disposition
        <select aria-label={"Board portal appeal outcome " + appeal.appeal_id}
          value={choices[appeal.appeal_id] || "UPHELD"}
          onChange={event => setChoices(prev => ({
            ...prev, [appeal.appeal_id]: event.target.value as "UPHELD" | "VACATED",
          }))}
          className="mt-1 block rounded border p-2">
          <option value="UPHELD">UPHELD</option>
          <option value="VACATED">VACATED</option>
        </select>
      </label>
      <label className="block text-sm">Board disposition explanation
        <textarea aria-label={"Board portal appeal explanation " + appeal.appeal_id}
          maxLength={2000} value={notes[appeal.appeal_id] || ""}
          onChange={event => setNotes(prev => ({
            ...prev, [appeal.appeal_id]: event.target.value,
          }))}
          className="mt-1 block w-full rounded border p-2"/>
      </label>
      <button type="button" disabled={busy || (notes[appeal.appeal_id] || "").trim().length < 3}
        onClick={() => { void decide(appeal); }}
        className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        Record my board appeal decision
      </button>
    </article>)}
  </section>;
}
