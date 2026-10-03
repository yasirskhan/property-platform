"use client";

import { useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";

type Preview = {
  total: number; create_count: number; conflict_rows: number[];
  preview_digest: string; can_commit: boolean; note: string;
};

export default function ContactTransferPanel({ canWrite, onImported }: {
  canWrite: boolean; onImported: () => Promise<void>;
}) {
  const [content, setContent] = useState("");
  const [fileName, setFileName] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function pick(file: File | undefined) {
    setError(""); setMessage(""); setPreview(null); setConfirmed(false);
    setContent(""); setFileName("");
    if (!file) return;
    if (file.size > 131072) {
      setError("CSV exceeds the 128 KiB limit.");
      return;
    }
    try {
      const text = await file.text();
      setContent(text);
      setFileName(file.name);
    } catch {
      setError("Cannot read the selected CSV file.");
    }
  }

  async function dryRun() {
    setBusy(true); setError(""); setMessage(""); setPreview(null); setConfirmed(false);
    try {
      const result = await apiPost("/api/contacts/import/preview", { csv_text: content }) as Preview;
      setPreview(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "CSV preview failed.");
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!preview?.can_commit || !confirmed) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost("/api/contacts/import/commit", {
        csv_text: content, preview_digest: preview.preview_digest, confirm: true,
      }) as { created: number };
      setMessage(`${result.created} contacts imported. No login accounts or vendor companies were created.`);
      setPreview(null); setContent(""); setFileName(""); setConfirmed(false);
      await onImported();
    } catch (cause) {
      setPreview(null); setConfirmed(false);
      setError(cause instanceof Error ? cause.message : "CSV changed; preview again.");
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await apiFetch("/api/contacts/export.csv", {
        method: "GET", headers: { Accept: "text/csv" },
      });
      if (!response.ok) throw new Error(`Export unavailable (${response.status}).`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = "contacts-export.csv"; link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Contacts export failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border bg-white p-4">
      <h2 className="text-lg font-semibold">Contacts CSV import / export</h2>
      <p className="mt-1 text-sm text-slate-600">
        Active, non-login Contacts only; no Users, Vendors, W-9s or tax data.
        Export is permission-gated. A preview is required before any import.
        Import creates new contacts only; it never merges or replaces records.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <button type="button" disabled={busy} onClick={() => { void download(); }}
          className="rounded border px-3 py-2 text-sm disabled:opacity-50">Export active contacts CSV</button>
        {canWrite && <>
          <label className="text-sm text-slate-700">
            Choose CSV (128 KiB / 200 rows max)
            <input type="file" accept=".csv,text/csv" onChange={(event) => { void pick(event.target.files?.[0]); }}
              className="mt-1 block max-w-full text-sm" />
          </label>
          <button type="button" disabled={busy || !content} onClick={() => { void dryRun(); }}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            Preview import
          </button>
        </>}
      </div>
      {fileName && <p className="mt-2 text-xs text-slate-500">Selected: {fileName}</p>}
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-2 text-sm text-green-700">{message}</p>}
      {canWrite && preview && <div className="mt-3 rounded-lg border p-3 text-sm">
        <p>{preview.total} rows; {preview.create_count} new contacts; {preview.conflict_rows.length} conflicts.</p>
        {preview.conflict_rows.length > 0 && <p className="mt-1 text-red-700">
          Conflicts at CSV rows {preview.conflict_rows.join(", ")}.
          Correct the file and preview again; no partial import is performed.
        </p>}
        {preview.can_commit && <>
          <label className="mt-2 flex items-center gap-2">
            <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
            I reviewed the CSV and authorize creation of {preview.create_count} contacts.
          </label>
          <button type="button" disabled={!confirmed || busy} onClick={() => { void commit(); }}
            className="mt-2 rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
            {busy ? "Importing…" : "Import reviewed contacts"}
          </button>
        </>}
      </div>}
    </section>
  );
}
