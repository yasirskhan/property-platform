"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Category = "CUSTOM" | "THREE_DAY_NOTICE";
type Letter = {
  id: number; title: string; category: Category;
  subject: string; body: string;
};
type Preview = {
  title: string; category: Category; subject: string; body: string;
  recipient_email: string; tenant_id: number; lease_id: number;
  property_id: number; legal_notice_review_required: boolean;
  review_token: string;
};
type Lease = { id: number; unit_id: number; status: string };
type Viewer = { id: number; role: string };
type Draft = { title: string; category: Category; subject: string; body: string };

const BASE = "/api/reporting/letters";
const TAGS = ["tenant_name", "tenant_email", "property_name", "property_address",
  "unit_number", "lease_start", "lease_end", "monthly_rent", "organization_name"];
function fresh(): Draft {
  return { title: "", category: "CUSTOM", subject: "", body: "" };
}

export default function LettersPage() {
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [letters, setLetters] = useState<Letter[]>([]);
  const [leases, setLeases] = useState<Lease[]>([]);
  const [draft, setDraft] = useState<Draft>(fresh());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [leaseId, setLeaseId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmRecipient, setConfirmRecipient] = useState(false);
  const [confirmContent, setConfirmContent] = useState(false);
  const [confirmLegal, setConfirmLegal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const [me, rows, leaseRows] = await Promise.all([
          apiGet("/auth/me") as Promise<Viewer>,
          apiGet(BASE) as Promise<Letter[]>,
          apiGet("/leases") as Promise<Lease[]>,
        ]);
        if (!mounted) return;
        setViewer(me);
        setLetters(rows);
        setLeases(leaseRows.filter((item) => String(item.status).toLowerCase() === "active"));
      } catch (cause) {
        if (mounted) setError(cause instanceof Error ? cause.message : "Unable to load letters.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void load();
    return () => { mounted = false; };
  }, []);

  function clearReview() {
    setPreview(null);
    setConfirmRecipient(false);
    setConfirmContent(false);
    setConfirmLegal(false);
  }

  function select(item: Letter) {
    setSelectedId(item.id);
    setEditingId(item.id);
    setDraft({ title: item.title, category: item.category,
               subject: item.subject, body: item.body });
    clearReview();
    setError("");
    setMessage("");
  }

  function startNew() {
    setEditingId(null);
    setSelectedId(null);
    setDraft(fresh());
    clearReview();
    setError("");
    setMessage("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (viewer?.role !== "ADMIN") return;
    setBusy(true); setError(""); setMessage("");
    try {
      const item = (editingId === null
        ? await apiPost(BASE, draft)
        : await apiPut(BASE + "/" + editingId, draft)) as Letter;
      setLetters((old) => editingId === null
        ? [...old, item]
        : old.map((row) => row.id === item.id ? item : row));
      setEditingId(item.id);
      setSelectedId(item.id);
      clearReview();
      setMessage("Letter template saved. Preview the saved version before delivery.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save letter.");
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(id: number) {
    if (!window.confirm("Deactivate this saved letter template?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(BASE + "/" + id);
      setLetters((old) => old.filter((item) => item.id !== id));
      if (selectedId === id) setSelectedId(null);
      if (editingId === id) { setEditingId(null); setDraft(fresh()); }
      clearReview();
      setMessage("Letter template deactivated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to deactivate letter.");
    } finally {
      setBusy(false);
    }
  }

  async function loadPreview() {
    if (selectedId === null || !leaseId) return;
    clearReview();
    setError(""); setMessage(""); setBusy(true);
    try {
      const value = await apiGet(BASE + "/" + selectedId + "/preview/" + Number(leaseId)) as Preview;
      setPreview(value);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to preview letter.");
    } finally {
      setBusy(false);
    }
  }

  async function emailPreview() {
    if (!preview || selectedId === null || !confirmRecipient || !confirmContent
        || (preview.legal_notice_review_required && !confirmLegal)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(BASE + "/" + selectedId + "/email", {
        lease_id: preview.lease_id,
        review_token: preview.review_token,
        confirm_recipient: confirmRecipient,
        confirm_content_reviewed: confirmContent,
        confirm_legal_review: confirmLegal,
      });
      clearReview();
      setMessage("Reviewed letter sent to the configured email delivery service.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to email letter.");
      clearReview();
    } finally {
      setBusy(false);
    }
  }

  const admin = viewer?.role === "ADMIN";
  return (
    <div className="space-y-5">
      <div className="print:hidden">
        <Link href="/dashboard/reporting" className="text-sm text-slate-600 hover:text-slate-900">← Reports</Link>
      </div>
      <header className="print:hidden">
        <h1 className="text-2xl font-bold text-slate-900">Letters</h1>
        <p className="mt-1 text-sm text-slate-500">
          Save templates, merge verified current-lease details, print, and email only after review.
        </p>
      </header>
      {loading && <p className="print:hidden text-sm text-slate-500">Loading letters…</p>}
      {error && <p role="alert" className="print:hidden rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="print:hidden rounded-lg border border-green-200 p-3 text-sm text-green-700">{message}</p>}

      <section className="print:hidden rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Letters overview</h2>
          {admin && <button type="button" onClick={startNew}
            className="rounded-lg border px-3 py-2 text-sm">New custom letter</button>}
        </div>
        {letters.length === 0 && !loading && <p className="mt-3 text-sm text-slate-500">No saved letters yet.</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          {letters.map((item) => (
            <button key={item.id} type="button" onClick={() => select(item)}
              aria-pressed={selectedId === item.id}
              className={"rounded-lg border px-3 py-2 text-left text-sm " +
                (selectedId === item.id ? "border-slate-900 bg-slate-100" : "border-slate-300")}>
              <span className="font-medium">{item.title}</span>
              <span className="ml-2 text-xs text-slate-500">
                {item.category === "THREE_DAY_NOTICE" ? "3-day draft" : "Custom"}
              </span>
            </button>
          ))}
        </div>
      </section>

      {admin && (
        <section className="print:hidden rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold">{editingId === null ? "Create letter" : "View / edit template"}</h2>
          <p className="mt-1 text-sm text-slate-500">
            Text-only mail merge. Supported tags: {TAGS.map((tag) => "{{" + tag + "}}").join(", ")}.
          </p>
          <form onSubmit={(event) => { void save(event); }} className="mt-3 space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-medium">Template title
                <input required maxLength={120} value={draft.title}
                  onChange={(event) => setDraft((old) => ({ ...old, title: event.target.value }))}
                  className="mt-1 block w-full rounded-lg border p-2" />
              </label>
              <label className="block text-sm font-medium">Category
                <select value={draft.category}
                  onChange={(event) => {
                    setDraft((old) => ({ ...old, category: event.target.value as Category }));
                    clearReview();
                  }}
                  className="mt-1 block w-full rounded-lg border p-2">
                  <option value="CUSTOM">Custom letter</option>
                  <option value="THREE_DAY_NOTICE">3-day notice — review required</option>
                </select>
              </label>
            </div>
            {draft.category === "THREE_DAY_NOTICE" && (
              <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                This is an editable draft, not a jurisdiction-approved legal notice.
                Verify local law, grounds, notice language, dates and service requirements.
                Email alone may not constitute valid statutory service.
              </p>
            )}
            <label className="block text-sm font-medium">Email subject
              <input required maxLength={180} value={draft.subject}
                onChange={(event) => { setDraft((old) => ({ ...old, subject: event.target.value })); clearReview(); }}
                className="mt-1 block w-full rounded-lg border p-2" />
            </label>
            <label className="block text-sm font-medium">Body — plain text
              <textarea required rows={8} maxLength={12000} value={draft.body}
                onChange={(event) => { setDraft((old) => ({ ...old, body: event.target.value })); clearReview(); }}
                className="mt-1 block w-full rounded-lg border p-2 font-mono text-sm" />
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="submit" disabled={busy}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                {busy ? "Saving…" : "Save template"}
              </button>
              {editingId !== null && <button type="button" disabled={busy}
                onClick={() => { void deactivate(editingId); }}
                className="rounded-lg border px-3 py-2 text-sm text-red-700">Deactivate</button>}
            </div>
          </form>
        </section>
      )}

      <section className="print:hidden rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold">Preview and deliver</h2>
        <p className="mt-1 text-sm text-slate-500">
          The server rechecks the recipient, lease, property assignment and permissions
          at preview and again before emailing. Unsaved editor changes are not deliverable.
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="block text-sm font-medium">Saved letter
            <select value={selectedId ?? ""}
              onChange={(event) => {
                const selected = letters.find((item) => item.id === Number(event.target.value));
                if (selected) select(selected);
                else { setSelectedId(null); clearReview(); }
              }}
              className="mt-1 block w-64 max-w-full rounded-lg border p-2">
              <option value="">Choose a template</option>
              {letters.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium">Current tenant lease
            <select value={leaseId}
              onChange={(event) => { setLeaseId(event.target.value); clearReview(); }}
              className="mt-1 block w-64 max-w-full rounded-lg border p-2">
              <option value="">Choose active lease</option>
              {leases.map((item) => (
                <option key={item.id} value={item.id}>Lease #{item.id} · Unit #{item.unit_id}</option>
              ))}
            </select>
          </label>
          <button type="button" disabled={busy || !selectedId || !leaseId}
            onClick={() => { void loadPreview(); }}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
            {busy ? "Loading…" : "Preview letter"}
          </button>
        </div>
      </section>

      {preview && (
        <>
          <section className="print:hidden space-y-3 rounded-xl border border-slate-200 bg-white p-4">
            {preview.legal_notice_review_required && (
              <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                Three-day draft: independently verify jurisdiction, precise legal language,
                amount and permitted delivery method. This app does not establish valid service.
              </p>
            )}
            <p className="text-sm font-medium">Recipient: {preview.recipient_email}</p>
            <p className="text-sm text-slate-500">
              Lease #{preview.lease_id} · Property #{preview.property_id}
            </p>
            <button type="button" onClick={() => window.print()}
              className="rounded-lg border px-3 py-2 text-sm">Print preview</button>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={confirmRecipient}
                onChange={(event) => setConfirmRecipient(event.target.checked)} />
              I verified the intended tenant and current email address.
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={confirmContent}
                onChange={(event) => setConfirmContent(event.target.checked)} />
              I reviewed the full rendered content of this letter.
            </label>
            {preview.legal_notice_review_required && (
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" checked={confirmLegal}
                  onChange={(event) => setConfirmLegal(event.target.checked)} />
                I independently reviewed the local legal requirements and service method.
              </label>
            )}
            <button type="button"
              disabled={busy || !confirmRecipient || !confirmContent
                || (preview.legal_notice_review_required && !confirmLegal)}
              onClick={() => { void emailPreview(); }}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              {busy ? "Sending…" : "Email reviewed letter"}
            </button>
          </section>
          <article aria-label="Printable letter preview"
            className="rounded-xl border border-slate-200 bg-white p-6 print:rounded-none print:border-none print:p-0">
            <h2 className="text-xl font-semibold">{preview.subject}</h2>
            <p className="mt-1 text-sm text-slate-500 print:text-black">
              To: {preview.recipient_email}
            </p>
            <pre className="mt-5 whitespace-pre-wrap break-words font-sans text-sm leading-7">
              {preview.body}
            </pre>
          </article>
        </>
      )}
    </div>
  );
}
