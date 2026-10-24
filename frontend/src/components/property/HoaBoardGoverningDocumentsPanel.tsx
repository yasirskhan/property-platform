"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiGet } from "@/lib/api";

type BoardDocument = {
  id: number;
  association_id: number;
  property_id: number;
  evidence_type: string;
  filename: string;
  recorded_at: string;
  status: "STAFF_SUPPLIED_UNVERIFIED";
};

export default function HoaBoardGoverningDocumentsPanel() {
  const [documents, setDocuments] = useState<BoardDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    void (apiGet("/api/hoa/board/my-governing-documents") as Promise<BoardDocument[]>)
      .then(rows => { if (live) setDocuments(rows); })
      .catch(cause => {
        if (live) setError(cause instanceof Error ? cause.message : "Board documents unavailable.");
      }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  async function download(row: BoardDocument) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await apiFetch(
        "/api/hoa/board/governing-documents/" + row.id, { method: "GET" },
      );
      if (!response.ok) throw new Error(
        "This private board document is unavailable or access was revoked.",
      );
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = row.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Document unavailable.");
    } finally { setBusy(false); }
  }

  return <section className="space-y-3 rounded border bg-white p-4">
    <h2 className="font-semibold">My HOA board documents</h2>
    <p className="text-xs text-slate-600">
      Only private documents expressly indexed to your current association and property
      board delegation appear. These are staff-supplied and unverified, not a
      certification of legal authority, adopted rules, or notice delivery.
      Downloads do not provide general staff attachment access.
    </p>
    {loading && <p className="text-xs">Loading board documents…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!loading && documents.length === 0 && !error &&
      <p className="text-sm">No private governing documents are available for your board seat.</p>}
    {documents.map(row => <article key={row.id}
      className="space-y-1 rounded border bg-slate-50 p-3 text-sm">
      <h3 className="font-medium break-all">{row.filename}</h3>
      <p className="text-xs">Association #{row.association_id}
        {" · "}Property #{row.property_id} · {row.evidence_type.replaceAll("_", " ")}
        {" · "}Staff-supplied / unverified</p>
      <button type="button" disabled={busy} className="text-blue-700 disabled:opacity-50"
        onClick={() => { void download(row); }}>
        Download private board document
      </button>
    </article>)}
  </section>;
}
