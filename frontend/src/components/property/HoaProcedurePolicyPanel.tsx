"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";

type Rule = {
  id: number;
  revision: number;
  jurisdiction_state: string | null;
  jurisdiction_locality: string | null;
  notice_preparation_days: number | null;
  cure_preparation_days: number | null;
  hearing_request_days: number | null;
  proposed_fine_cap: string | null;
  draft_notice_text: string | null;
  supporting_evidence_id: number | null;
  issuance_enabled: false;
  status: "STAFF_CONFIGURED_UNVERIFIED";
};
type Source = {
  id: number; evidence_type: string; filename: string;
  status: "STAFF_SUPPLIED_UNVERIFIED";
};
type Form = {
  jurisdiction_state: string;
  jurisdiction_locality: string;
  notice_preparation_days: string;
  cure_preparation_days: string;
  hearing_request_days: string;
  proposed_fine_cap: string;
  draft_notice_text: string;
  supporting_evidence_id: string;
};
const EMPTY: Form = {
  jurisdiction_state: "", jurisdiction_locality: "",
  notice_preparation_days: "", cure_preparation_days: "",
  hearing_request_days: "", proposed_fine_cap: "",
  draft_notice_text: "", supporting_evidence_id: "",
};

export default function HoaProcedurePolicyPanel({
  associationId, propertyId, canEdit, onClose,
}: {
  associationId: number; propertyId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const [saved, setSaved] = useState<Rule | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = "/api/hoa/associations/" + associationId;
  const query = "?property_id=" + propertyId;

  useEffect(() => {
    let live = true;
    setLoading(true); setError(""); setMessage("");
    void Promise.all([
      apiGet(base + "/procedure-policy" + query) as Promise<Rule | null>,
      (apiGet(base + "/governing-evidence" + query) as Promise<Source[]>)
        .catch(() => []),
    ]).then(([result, documents]) => {
      if (!live) return;
      setSaved(result);
      setSources(documents);
      setForm(result ? {
        jurisdiction_state: result.jurisdiction_state || "",
        jurisdiction_locality: result.jurisdiction_locality || "",
        notice_preparation_days: result.notice_preparation_days?.toString() || "",
        cure_preparation_days: result.cure_preparation_days?.toString() || "",
        hearing_request_days: result.hearing_request_days?.toString() || "",
        proposed_fine_cap: result.proposed_fine_cap || "",
        draft_notice_text: result.draft_notice_text || "",
        supporting_evidence_id: result.supporting_evidence_id?.toString() || "",
      } : EMPTY);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Procedure settings unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [base, query]);

  function set(key: keyof Form, value: string) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    const integer = (value: string) => value === "" ? null : Number(value);
    try {
      const result = await apiPut(base + "/procedure-policy", {
        property_id: propertyId,
        jurisdiction_state: form.jurisdiction_state.trim() || null,
        jurisdiction_locality: form.jurisdiction_locality.trim() || null,
        notice_preparation_days: integer(form.notice_preparation_days),
        cure_preparation_days: integer(form.cure_preparation_days),
        hearing_request_days: integer(form.hearing_request_days),
        proposed_fine_cap: form.proposed_fine_cap || null,
        draft_notice_text: form.draft_notice_text.trim() || null,
        supporting_evidence_id: integer(form.supporting_evidence_id),
      }) as Rule;
      setSaved(result);
      setMessage("Staff settings recorded; no legal notices, fines or dues are enabled.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save procedure settings.");
    } finally {
      setBusy(false);
    }
  }

  const input = (field: keyof Form, label: string) => (
    <label className="block text-xs">{label}
      <input value={form[field]} disabled={!canEdit || busy}
        onChange={(event) => set(field, event.target.value)}
        type={field.endsWith("_days") ? "number" : field === "proposed_fine_cap" ? "number" : "text"}
        min={field.endsWith("_days") || field === "proposed_fine_cap" ? "0" : undefined}
        max={field.endsWith("_days") ? "366" : undefined}
        step={field === "proposed_fine_cap" ? "0.01" : undefined}
        className="mt-1 block w-full rounded border bg-white p-2" />
    </label>
  );

  return (
    <section className="w-full space-y-3 rounded border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">HOA staff procedure configuration</h3>
        <button type="button" onClick={onClose} className="text-blue-700">Close</button>
      </div>
      <p className="text-xs text-amber-800">
        All fields are staff-entered and unverified. No jurisdiction defaults
        or statutory periods are hardcoded. A saved rule or attached document
        does not verify law, authorize a board, send a notice, levy a fine,
        create a charge or book reserves. Obtain independent legal review
        before using these assumptions in any official workflow.
      </p>
      {loading && <p className="text-xs">Loading…</p>}
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      {message && <p role="status" className="text-xs text-green-700">{message}</p>}
      {!loading && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-3">
          <p className="text-xs text-slate-600">
            {saved ? "Staff revision " + saved.revision : "No rules recorded"}
            {" · "}Legal issuance remains disabled
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {input("jurisdiction_state", "Recorded state / jurisdiction")}
            {input("jurisdiction_locality", "Recorded county / locality")}
            {input("notice_preparation_days", "Proposed notice preparation days")}
            {input("cure_preparation_days", "Proposed cure-tracking days")}
            {input("hearing_request_days", "Proposed hearing request days")}
            {input("proposed_fine_cap", "Proposed fine cap (not assessed)")}
          </div>
          <label className="block text-xs">Staff draft notice language (not delivered)
            <textarea maxLength={4000} rows={4} value={form.draft_notice_text}
              disabled={!canEdit || busy}
              onChange={(event) => set("draft_notice_text", event.target.value)}
              className="mt-1 block w-full rounded border bg-white p-2" />
          </label>
          <label className="block text-xs">Optional private supporting evidence reference
            <select value={form.supporting_evidence_id}
              disabled={!canEdit || busy}
              onChange={(event) => set("supporting_evidence_id", event.target.value)}
              className="mt-1 block w-full rounded border bg-white p-2">
              <option value="">No source linked (unverified)</option>
              {sources.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.evidence_type} · {row.filename} · STAFF SUPPLIED
                </option>
              ))}
            </select>
          </label>
          {canEdit && (
            <button type="submit" disabled={busy}
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : "Save staff procedure settings"}
            </button>
          )}
        </form>
      )}
    </section>
  );
}
