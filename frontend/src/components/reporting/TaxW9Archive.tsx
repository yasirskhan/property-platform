"use client";

import { useEffect, useState } from "react";

import { apiFetch, apiGet } from "@/lib/api";

type RecipientProfile = {
  id: number;
  subject_type: string;
  subject_id: number;
  tin_last4: string;
};

type ArchivedW9 = {
  id: number;
  tax_profile_id: number;
  size_bytes: number;
  received_on: string;
  uploaded_at: string;
  uploaded_by_id: number | null;
};

export default function TaxW9Archive({
  profiles,
  onArchived,
}: {
  profiles: RecipientProfile[];
  onArchived: (profileId: number, receivedOn: string) => void;
}) {
  const recipients = profiles.filter((item) =>
    item.subject_type === "OWNER" || item.subject_type === "VENDOR"
  );
  const [chosen, setChosen] = useState("");
  const selectedId = recipients.some((item) => String(item.id) === chosen)
    ? Number(chosen) : recipients[0]?.id ?? 0;
  const [entries, setEntries] = useState<ArchivedW9[]>([]);
  const [pdf, setPdf] = useState<File | null>(null);
  const [receivedOn, setReceivedOn] = useState("");
  const [signedReviewed, setSignedReviewed] = useState(false);
  const [busy, setBusy] = useState<"upload" | "download" | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    apiGet(`/api/reporting/tax-w9/${selectedId}`)
      .then((items: ArchivedW9[]) => {
        if (active) setEntries(items);
      })
      .catch(() => {
        if (active) setError("Signed W-9 archive cannot be loaded.");
      });
    return () => { active = false; };
  }, [selectedId]);

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fileInput = event.currentTarget.querySelector<HTMLInputElement>('input[type="file"]');
    if (!selectedId || !pdf || !receivedOn || !signedReviewed) return;
    setError(""); setMessage("");
    if (pdf.size > 5 * 1024 * 1024 || !pdf.size) {
      setError("Choose a nonempty PDF no larger than 5 MB.");
      return;
    }
    setBusy("upload");
    try {
      const params = new URLSearchParams({
        received_on: receivedOn,
        signed_original_confirmed: "true",
      });
      // A raw PDF body is deliberate: multipart parsers can spool sensitive
      // originals to plaintext temporary files on the application server.
      const response = await apiFetch(
        `/api/reporting/tax-w9/${selectedId}?${params.toString()}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/pdf", Accept: "application/json" },
          body: pdf,
          cache: "no-store",
        }
      );
      if (!response.ok) {
        throw new Error(response.status === 503
          ? "Dedicated tax-profile encryption must be configured by the operator."
          : `W-9 archive request failed (${response.status}).`);
      }
      const document = await response.json() as ArchivedW9;
      setEntries((current) => [document, ...current.filter((row) =>
        row.tax_profile_id === document.tax_profile_id
      )]);
      onArchived(selectedId, receivedOn);
      setPdf(null); setSignedReviewed(false); setReceivedOn("");
      if (fileInput) fileInput.value = "";
      setMessage("Encrypted signed scan archived; staff attestation recorded. This is not an electronic W-9 signature.");
    } catch {
      // Do not reflect a file's contents or name in client error reports.
      setError("Unable to archive the PDF. Check permission, tax key, file and received date.");
    } finally {
      setBusy(null);
    }
  }

  async function download(documentId: number) {
    if (!selectedId) return;
    setBusy("download"); setError("");
    try {
      const response = await apiFetch(
        `/api/reporting/tax-w9/${selectedId}/${documentId}/download`,
        { method: "GET", headers: { Accept: "application/pdf" }, cache: "no-store" },
      );
      if (!response.ok) throw new Error("Archive download denied");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "signed-w9.pdf";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Download failed or you do not have access.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-slate-900">Restricted signed W-9 archive</h2>
      <p className="mt-1 text-sm text-slate-600">
        Scanned paper W-9 forms are encrypted separately from general attachments.
        Only organization administrators with reporting permission can access them.
        The PDF signature is confirmed by staff, not automatically verified by this software.
      </p>
      {recipients.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">Save an owner or vendor taxpayer profile first.</p>
      ) : (
        <>
          <form onSubmit={upload} className="mt-4 space-y-3">
            <label className="block text-sm font-medium text-slate-700">
              Owner or vendor taxpayer profile
              <select value={selectedId} onChange={(event) => {
                setChosen(event.target.value);
                setPdf(null); setSignedReviewed(false); setError(""); setMessage("");
              }} className="mt-1 block w-full max-w-lg rounded-lg border border-slate-300 p-2">
                {recipients.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.subject_type === "OWNER" ? "Owner" : "Vendor"} #{row.subject_id} · Tax ID ending {row.tin_last4}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Signed paper W-9 scan (PDF, maximum 5 MB)
              <input type="file" required accept="application/pdf,.pdf"
                onChange={(event) => setPdf(event.target.files?.[0] ?? null)}
                className="mt-1 block w-full text-sm" />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Paper W-9 received date
              <input required type="date" value={receivedOn}
                onChange={(event) => setReceivedOn(event.target.value)}
                className="mt-1 block rounded-lg border border-slate-300 p-2" />
            </label>
            <label className="flex items-start gap-2 text-sm text-slate-700">
              <input type="checkbox" required checked={signedReviewed}
                onChange={(event) => setSignedReviewed(event.target.checked)}
                className="mt-1" />
              <span>I reviewed the signed paper original or scan. This is a staff attestation,
                not an electronic signature by the payee.</span>
            </label>
            <button disabled={busy !== null || !pdf || !receivedOn || !signedReviewed}
              type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              {busy === "upload" ? "Encrypting…" : "Archive signed PDF"}
            </button>
          </form>
          {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
          {message && <p role="status" className="mt-3 text-sm text-green-700">{message}</p>}
          <div className="mt-5 border-t border-slate-200 pt-3">
            <h3 className="text-sm font-semibold text-slate-800">Archived paper W-9 scans</h3>
            {entries.filter((row) => row.tax_profile_id === selectedId).length === 0 && (
              <p className="mt-2 text-sm text-slate-500">No encrypted scans for this recipient.</p>
            )}
            {entries.filter((row) => row.tax_profile_id === selectedId).map((row) => (
              <div key={row.id} className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                <span>Received {row.received_on} · {(row.size_bytes / 1024).toFixed(0)} KB</span>
                <button type="button" disabled={busy !== null}
                  onClick={() => { void download(row.id); }}
                  className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-50">
                  Download restricted PDF
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
