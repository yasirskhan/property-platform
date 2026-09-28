"use client";
import { useEffect, useState } from "react";
import { apiFetch, apiGet } from "@/lib/api";

type Scan = {
  id: number;
  building_id: number;
  size_bytes: number;
  received_on: string;
  uploaded_at: string;
  uploaded_by_id: number | null;
};

export default function Affordable8609Archive({
  propertyId, programId, buildingId, onClose,
}: { propertyId: number; programId: number; buildingId: number; onClose: () => void }) {
  const [items, setItems] = useState<Scan[]>([]);
  const [pdf, setPdf] = useState<File | null>(null);
  const [receivedOn, setReceivedOn] = useState("");
  const [attested, setAttested] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const path = `/api/properties/${propertyId}/affordable-programs/${programId}/buildings/${buildingId}/8609-documents`;

  useEffect(() => {
    let live = true;
    setItems([]); setLoading(true); setError(""); setMessage("");
    void (async () => {
      try {
        const records = await apiGet(path) as Scan[];
        if (live) setItems(records);
      } catch {
        if (live) setError("Restricted Form 8609 scans cannot be loaded.");
      } finally { if (live) setLoading(false); }
    })();
    return () => { live = false; };
  }, [path]);

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.querySelector<HTMLInputElement>('input[type="file"]');
    if (!pdf || !receivedOn || !attested) return;
    setError(""); setMessage("");
    if (!pdf.size || pdf.size > 5 * 1024 * 1024) {
      setError("Choose a nonempty PDF not larger than 5 MB."); return;
    }
    setBusy(true);
    try {
      const params = new URLSearchParams({
        received_on: receivedOn, signed_copy_reviewed: "true",
      });
      const response = await apiFetch(`${path}?${params.toString()}`, {
        method: "POST",
        headers: { "Content-Type": "application/pdf", Accept: "application/json" },
        body: pdf, cache: "no-store",
      });
      if (!response.ok) throw new Error("Archive denied");
      const saved = await response.json() as Scan;
      setItems((prev) => [saved, ...prev]);
      setPdf(null); setReceivedOn(""); setAttested(false);
      if (input) input.value = "";
      setMessage("Encrypted staff scan archived. Signature authenticity and IRS filing remain unverified.");
    } catch {
      // No original filename, scanned contents or sensitive request text in errors.
      setError("Cannot archive the scan. Check access, PDF, date and operator compliance encryption key.");
    } finally { setBusy(false); }
  }

  async function download(id: number) {
    setBusy(true); setError("");
    try {
      const response = await apiFetch(`${path}/${id}/download`, {
        headers: { Accept: "application/pdf" }, cache: "no-store",
      });
      if (!response.ok) throw new Error("Download denied");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = "form-8609-staff-scan.pdf";
      anchor.click(); URL.revokeObjectURL(url);
    } catch { setError("Download unavailable or access denied."); }
    finally { setBusy(false); }
  }

  return (
    <section className="rounded border border-amber-200 bg-amber-50 p-4 text-sm" aria-label="Restricted Form 8609 scan archive">
      <div className="flex items-start justify-between gap-3">
        <h4 className="font-semibold">Restricted Form 8609 scans · Building #{buildingId}</h4>
        <button type="button" onClick={onClose} className="rounded border px-2 py-1">Close</button>
      </div>
      <p className="mt-2">
        Archive one scan per agency document, including separate allocations as necessary.
        Access is restricted to authorized administrators or owners. Staff attestation
        only records that a scan was reviewed; it cannot prove agency issuance,
        signature authenticity, eligible basis, credit allocation, IRS receipt or filing.
        Do not upload through generic attachments. PDFs are not malware-scanned.
      </p>
      <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={(event) => { void upload(event); }}>
        <label className="block">Form 8609 scanned PDF (max 5 MB)
          <input type="file" required accept="application/pdf,.pdf"
            onChange={(event) => setPdf(event.target.files?.[0] || null)}
            className="mt-1 block" />
        </label>
        <label className="block">Staff-recorded date received
          <input type="date" required value={receivedOn}
            onChange={(event) => setReceivedOn(event.target.value)}
            className="mt-1 block rounded border p-2" />
        </label>
        <label className="flex max-w-sm items-start gap-2">
          <input type="checkbox" required checked={attested}
            onChange={(event) => setAttested(event.target.checked)}
            className="mt-1" />
          <span>I reviewed the supplied scan and understand that this does not independently verify agency issuance or IRS filing.</span>
        </label>
        <button type="submit" disabled={busy || !pdf || !receivedOn || !attested}
          className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
          {busy ? "Working…" : "Archive encrypted scan"}
        </button>
      </form>
      {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
      {message && <p role="status" className="mt-2 text-green-800">{message}</p>}
      {loading && <p className="mt-2">Loading restricted archive…</p>}
      {!loading && items.length === 0 && <p className="mt-2">No archived scans for this building.</p>}
      <div className="mt-2 space-y-2">
        {items.map((row) => (
          <div key={row.id} className="flex items-center justify-between gap-2 rounded border bg-white p-2">
            <span>Received {row.received_on} · {(row.size_bytes / 1024).toFixed(0)} KB · staff scan</span>
            <button type="button" disabled={busy} className="rounded border px-2 py-1"
              onClick={() => { void download(row.id); }}>Download</button>
          </div>
        ))}
      </div>
    </section>
  );
}
