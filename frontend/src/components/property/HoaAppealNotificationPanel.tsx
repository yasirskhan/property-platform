"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Template = { id: number; title: string; subject: string; body: string };
type Delivery = {
  id: number; appeal_id: number; template_id: number; outcome: "UPHELD" | "VACATED";
  status: "PENDING" | "SENDING" | "FAILED" | "TEST_ONLY" | "SMTP_ACCEPTED";
  attempt_count: number; smtp_accepted_at: string | null;
  actual_delivery_confirmed: false; legally_served: false; accounting_modified: false;
};

export default function HoaAppealNotificationPanel({
  associationId, propertyId, caseId, appealId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number; appealId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId + "/staff-cases/" + caseId + "/fine";
  const route = base + "/appeals/" + appealId + "/notifications";
  const query = "?property_id=" + propertyId;
  const [templates, setTemplates] = useState<Template[]>([]);
  const [history, setHistory] = useState<Delivery[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKey = useRef("");

  async function refresh() {
    const [options, rows] = await Promise.all([
      apiGet(base + "/appeal-email-templates" + query) as Promise<Template[]>,
      apiGet(route + query) as Promise<Delivery[]>,
    ]);
    setTemplates(options); setHistory(rows);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base + "/appeal-email-templates" + query) as Promise<Template[]>,
      apiGet(route + query) as Promise<Delivery[]>,
    ]).then(([options, rows]) => {
      if (live) { setTemplates(options); setHistory(rows); }
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Appeal email history unavailable.");
    });
    return () => { live = false; };
  }, [base, route, query]);

  function summary(row: Delivery): string {
    if (row.status === "TEST_ONLY") return "Test-only: no real email was transmitted.";
    if (row.status === "SMTP_ACCEPTED") return "SMTP accepted the message. Actual inbox delivery is unconfirmed.";
    if (row.status === "FAILED") return "Email attempt failed. An authorized board member may retry.";
    if (row.status === "SENDING") return "Email attempt in progress; an expired claim may be retried.";
    return "Email queued; sending is not yet confirmed.";
  }

  async function send() {
    if (!canEdit || busy || !selectedId || history.length) return;
    const template = templates.find((item) => item.id === Number(selectedId));
    if (!template || !window.confirm(
      "Send the recorded board appeal outcome to the case's verified responsible member using this customer-authored template? This cannot be recalled."
    )) return;
    if (!requestKey.current) requestKey.current = crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      const row = await apiPost(route, {
        property_id: propertyId, template_id: template.id,
        request_key: requestKey.current,
      }) as Delivery;
      requestKey.current = "";
      await refresh();
      setMessage(summary(row));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Appeal outcome email unavailable.");
      await refresh().catch(() => {});
    } finally { setBusy(false); }
  }

  async function retry(row: Delivery) {
    if (!canEdit || busy || !window.confirm(
      "Retry the same recorded appeal outcome email to its original verified recipient? A previous SMTP attempt may have reached the inbox."
    )) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost(route + "/" + row.id + "/retry" + query) as Delivery;
      await refresh();
      setMessage(summary(result));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Appeal email retry unavailable.");
      await refresh().catch(() => {});
    } finally { setBusy(false); }
  }

  const selected = templates.find((item) => item.id === Number(selectedId));
  return <section className="space-y-2 rounded border border-blue-200 bg-blue-50 p-3 text-xs">
    <div className="flex items-center justify-between">
      <h5 className="font-semibold">Fine appeal outcome email</h5>
      <button type="button" className="text-blue-700" onClick={onClose}>Close appeal email</button>
    </div>
    <p>An authorized association board member can explicitly send the recorded UPHELD or VACATED
      outcome to the original verified responsible member. This uses an organization-authored
      CUSTOM letter template named &quot;HOA Appeal: ...&quot;. Organization and property merge tags
      are available. The recorded outcome and decision date are appended automatically.
      Sending never changes the fine, receipt or general ledger. Email acceptance does not
      establish inbox delivery or legal notice service.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {history.length === 0 && <>
      <label className="block">Appeal outcome letter template
        <select aria-label="Appeal outcome letter template" value={selectedId}
          onChange={(event) => { setSelectedId(event.target.value); requestKey.current = ""; }}
          className="mt-1 block w-full rounded border p-2">
          <option value="">Choose an association-authored template</option>
          {templates.map((row) => <option key={row.id} value={row.id}>{row.title}</option>)}
        </select>
      </label>
      {selected && <div className="rounded border bg-white p-2">
        <p className="font-semibold">Customer-authored text preview</p>
        <p>Subject: {selected.subject}</p>
        <p className="whitespace-pre-wrap">{selected.body}</p>
        <p>The final board outcome and date are appended at send time.</p>
      </div>}
      {templates.length === 0 && <p>Create an active CUSTOM letter template titled
        &quot;HOA Appeal: ...&quot; in Reporting Letters before sending.</p>}
      <button type="button" disabled={!canEdit || busy || !selectedId}
        className="rounded bg-blue-900 px-3 py-2 text-white disabled:opacity-50"
        onClick={() => { void send(); }}>Authorize and email appeal outcome</button>
    </>}
    <h6 className="font-semibold">Outcome email attempts</h6>
    {history.length === 0 && <p>No outcome email has been requested.</p>}
    {history.map((row) => <div key={row.id} className="space-y-1 rounded border bg-white p-2">
      <p>Email #{row.id} · {row.outcome} · {row.status.replaceAll("_", " ")} · Attempts {row.attempt_count}</p>
      <p>{summary(row)}</p>
      {row.smtp_accepted_at && <p>SMTP acceptance recorded: {row.smtp_accepted_at}</p>}
      {row.status !== "SMTP_ACCEPTED" && canEdit && <button type="button"
        disabled={busy} className="text-blue-700 disabled:opacity-50"
        onClick={() => { void retry(row); }}>Retry appeal outcome email</button>}
    </div>)}
    <button type="button" disabled={busy} className="text-blue-700 disabled:opacity-50"
      onClick={() => { void refresh().catch((cause) => {
        setError(cause instanceof Error ? cause.message : "Refresh failed.");
      }); }}>Refresh email history</button>
  </section>;
}
