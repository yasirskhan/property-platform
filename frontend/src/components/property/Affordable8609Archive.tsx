"use client";
import { useEffect, useState } from "react";
import { apiFetch, apiGet } from "@/lib/api";

type RotationPage = {
  checked: number;
  pending_rewrap: number;
  current_key: number;
  next_document_id: number;
  has_more: boolean;
};

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
  const [isAdmin, setIsAdmin] = useState(false);
  const [rotation, setRotation] = useState<RotationPage | null>(null);
  const [rotationBusy, setRotationBusy] = useState(false);
  const [rotationError, setRotationError] = useState("");
  const path = `/api/properties/${propertyId}/affordable-programs/${programId}/buildings/${buildingId}/8609-documents`;

  useEffect(() => {
    let live = true;
    setItems([]); setLoading(true); setError(""); setMessage("");
    setRotation(null); setRotationError(""); setIsAdmin(false);
    void (async () => {
      try {
        const records = await apiGet(path) as Scan[];
        const viewer = await apiGet("/auth/me") as { role: string };
        if (live) { setItems(records); setIsAdmin(viewer.role === "ADMIN"); }
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
      setRotation(null); setRotationError("");
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

  async function inspectRotation(cursor = 0, append = false) {
    if (rotationBusy || !isAdmin) return;
    setRotationBusy(true); setRotationError("");
    try {
      const page = await apiGet(
        `${path}/rotation-readiness?after_document_id=${cursor}&limit=20`
      ) as RotationPage;
      setRotation((previous) => append && previous ? {
        checked: previous.checked + page.checked,
        pending_rewrap: previous.pending_rewrap + page.pending_rewrap,
        current_key: previous.current_key + page.current_key,
        next_document_id: page.next_document_id,
        has_more: page.has_more,
      } : page);
    } catch {
      setRotationError(
        "Cannot inspect encryption-key readiness. Verify administrator access and the configured current and historical keys."
      );
    } finally { setRotationBusy(false); }
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
      {isAdmin && (
        <div className="mt-4 rounded border border-slate-300 bg-white p-3">
          <h5 className="font-semibold">Encryption-key readiness · this building only</h5>
          <p className="mt-1 text-xs text-slate-600">
            This check reads encrypted records without altering them. It cannot establish
            that a historical key is safe to remove: every page, building, and organization
            must be checked independently before retiring a shared key.
          </p>
          <button type="button" disabled={rotationBusy || busy}
            onClick={() => { void inspectRotation(); }}
            className="mt-2 rounded border px-3 py-1.5 text-sm disabled:opacity-50">
            {rotationBusy ? "Checking…" : "Check rotation status"}
          </button>
          {rotationError && <p role="alert" className="mt-2 text-sm text-red-700">{rotationError}</p>}
          {rotation && (
            <div role="status" className="mt-2 text-sm">
              Scans checked: {rotation.checked} · Need rewrap: {rotation.pending_rewrap} ·
              Current key: {rotation.current_key}
              {rotation.has_more && (
                <button type="button" disabled={rotationBusy}
                  onClick={() => { void inspectRotation(rotation.next_document_id, true); }}
                  className="ml-3 rounded border px-3 py-1 text-sm disabled:opacity-50">
                  Check next page
                </button>
              )}
              {!rotation.has_more && <p className="mt-1 text-xs text-slate-600">
                This building scan is complete for the selected key configuration;
                it is not an organization-wide or system-wide clearance.
              </p>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
