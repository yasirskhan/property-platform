"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import {
  emailOwnerPacket,
  listOwnerStatements,
  previewOwnerPacket,
  type OwnerPacketPreview,
  type OwnerStatement,
  type OwnerPacketSendResult,
} from "@/lib/ownerStatements";

type Me = { id: number; role: string };
const STAFF = new Set(["ADMIN", "MANAGER"]);

function PacketsContent() {
  const query = useSearchParams();
  const [user, setUser] = useState<Me | null>(null);
  const [statements, setStatements] = useState<OwnerStatement[]>([]);
  const [selected, setSelected] = useState(query.get("statement_id") || "");
  const [preview, setPreview] = useState<OwnerPacketPreview | null>(null);
  const [confirmRecipient, setConfirmRecipient] = useState(false);
  const [confirmReview, setConfirmReview] = useState(false);
  const [busy, setBusy] = useState<"load" | "preview" | "send" | null>("load");
  const [error, setError] = useState("");
  const [sent, setSent] = useState<OwnerPacketSendResult | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    let active = true;
    (async () => {
      const me = await apiGet("/auth/me") as Me;
      if (!active) return;
      setUser(me);
      if (!STAFF.has(me.role)) {
        setError("Only authorized staff can send owner packets.");
        return;
      }
      // Never fetch the organization-wide statement directory for managers.
      // Their explicit selection is authorized by each backend preview.
      if (me.role === "ADMIN") {
        const list = await listOwnerStatements({ limit: 200 });
        if (active) setStatements(list.items);
      }
    })().catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Owner statements unavailable.");
    }).finally(() => { if (active) setBusy(null); });
    return () => { active = false; generation.current += 1; };
  }, []);

  function changeStatement(value: string) {
    generation.current += 1;
    setSelected(value);
    setPreview(null);
    setSent(null);
    setError("");
    setConfirmRecipient(false);
    setConfirmReview(false);
  }

  async function loadPreview() {
    const id = Number(selected);
    if (!Number.isSafeInteger(id) || id <= 0) {
      setError("Select an existing frozen owner statement.");
      return;
    }
    const next = ++generation.current;
    setBusy("preview");
    setError("");
    setSent(null);
    setConfirmRecipient(false);
    setConfirmReview(false);
    setPreview(null);
    try {
      const value = await previewOwnerPacket(id);
      if (next === generation.current) setPreview(value);
    } catch (cause) {
      if (next === generation.current) {
        setError(cause instanceof Error ? cause.message : "Cannot prepare packet.");
      }
    } finally {
      if (next === generation.current) setBusy(null);
    }
  }

  async function sendPacket() {
    if (!preview || !preview.email_enabled || !confirmRecipient || !confirmReview || busy) return;
    if (String(preview.statement_id) !== selected) return;
    const next = ++generation.current;
    setBusy("send");
    setError("");
    setSent(null);
    try {
      const result = await emailOwnerPacket(preview.statement_id, preview.review_token);
      if (next === generation.current) {
        setSent(result);
        setPreview(null);
        setConfirmRecipient(false);
        setConfirmReview(false);
      }
    } catch (cause) {
      if (next === generation.current) {
        setError(cause instanceof Error ? cause.message : "Packet email failed. Review again before retrying.");
        // A stale recipient or settings change must always require a new preview.
        setPreview(null);
        setConfirmRecipient(false);
        setConfirmReview(false);
      }
    } finally {
      if (next === generation.current) setBusy(null);
    }
  }

  const canPrepare = user && STAFF.has(user.role);
  return (
    <div className="mx-auto max-w-4xl space-y-5 p-6">
      <nav className="flex flex-wrap gap-4 text-sm">
        <Link href="/dashboard/accounting/owner-statements" className="text-blue-700 hover:underline">
          ← Owner Statements
        </Link>
        <Link href="/dashboard/accounting/owner-statements/packet-settings" className="text-blue-700 hover:underline">
          Packet settings
        </Link>
      </nav>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Send Owner Packets</h1>
        <p className="mt-1 text-sm text-slate-600">
          Preview a frozen owner statement and its selected property cash summary,
          then confirm the current owner email before delivery.
        </p>
      </header>
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Packet attachments are <strong>CSV files, not PDFs</strong>. Figures come from the
        saved statement snapshot; this action does not post or recalculate accounting.
        Only the verified owner email on the current statement can receive the packet.
      </section>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {sent && (
        <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-900">
          Packet email sent to {sent.recipient_email} with {sent.filenames.length} CSV attachment(s).
        </p>
      )}
      {busy === "load" && <p className="text-sm text-slate-500">Loading statements…</p>}
      {canPrepare && (
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <label htmlFor="packet-statement" className="block text-sm font-medium text-slate-800">
            Frozen statement to send
          </label>
          {user.role === "ADMIN" && statements.length > 0 ? (
            <select
              id="packet-statement" value={selected}
              onChange={(event) => changeStatement(event.target.value)}
              className="mt-2 block w-full rounded-lg border border-slate-300 p-2 text-sm"
            >
              <option value="">Select a frozen statement</option>
              {selected && !statements.some((item) => String(item.id) === selected) && (
                <option value={selected}>Statement #{selected} (from link)</option>
              )}
              {statements.map((item) => (
                <option key={item.id} value={item.id}>
                  #{item.id} — {item.owner_name || item.owner_email || `Owner #${item.owner_id}`}
                  {" · "}{item.period_start} to {item.period_end}
                </option>
              ))}
            </select>
          ) : (
            <input id="packet-statement" type="number" min={1} step={1} inputMode="numeric"
              value={selected} onChange={(event) => changeStatement(event.target.value)}
              placeholder="Statement ID from Owner Statements"
              className="mt-2 block w-full rounded-lg border border-slate-300 p-2 text-sm" />
          )}
          <div className="mt-3">
            <button type="button" onClick={() => { void loadPreview(); }}
              disabled={!selected || busy !== null}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              {busy === "preview" ? "Preparing…" : "Preview packet"}
            </button>
          </div>
          {preview && (
            <div className="mt-5 space-y-4 border-t border-slate-200 pt-5">
              <h2 className="text-lg font-semibold text-slate-900">Review packet before sending</h2>
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <div><dt className="text-slate-500">Owner</dt><dd className="font-medium">Owner #{preview.owner_id}</dd></div>
                <div><dt className="text-slate-500">Current recipient</dt><dd className="break-all font-medium">{preview.recipient_email}</dd></div>
                <div><dt className="text-slate-500">Statement period</dt><dd>{preview.period_start} to {preview.period_end}</dd></div>
                <div><dt className="text-slate-500">Attachment format</dt><dd>{preview.attachment_format} (not PDF)</dd></div>
              </dl>
              {preview.cover_message && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Cover message</h3>
                  <p className="mt-1 whitespace-pre-wrap rounded bg-slate-50 p-3 text-sm">{preview.cover_message}</p>
                </div>
              )}
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Frozen CSV attachments</h3>
                <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
                  {preview.attachment_filenames.map((file) => <li key={file}>{file}</li>)}
                </ul>
              </div>
              {!preview.email_enabled ? (
                <p className="rounded-lg border border-amber-200 p-3 text-sm text-amber-900">
                  Owner packet email is disabled in packet settings. Enable it there and preview again.
                </p>
              ) : (
                <div className="space-y-3 border-t border-slate-200 pt-4">
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" checked={confirmRecipient}
                      onChange={(event) => setConfirmRecipient(event.target.checked)} className="mt-1" />
                    <span>I verified the current recipient email shown above belongs to this owner.</span>
                  </label>
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" checked={confirmReview}
                      onChange={(event) => setConfirmReview(event.target.checked)} className="mt-1" />
                    <span>I reviewed this frozen statement, cover message and the selected CSV attachments.</span>
                  </label>
                  <button type="button" onClick={() => { void sendPacket(); }}
                    disabled={!confirmRecipient || !confirmReview || busy !== null}
                    className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                    {busy === "send" ? "Sending…" : "Send packet email"}
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default function OwnerPacketsPage() {
  return <Suspense fallback={<div className="p-6 text-sm text-slate-500">Loading owner packets…</div>}>
    <PacketsContent />
  </Suspense>;
}
