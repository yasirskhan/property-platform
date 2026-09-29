"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import {
  downloadEntityAttachment, listEntityAttachments,
  type EntityAttachment,
} from "@/lib/entityAttachments";

type Evidence = {
  id: number; case_id: number; attachment_id: number;
  evidence_type: "PHOTO" | "DOCUMENT" | "OTHER";
  filename: string; recorded_at: string; private_only: true;
};

const SUPPORTED = /\.(pdf|doc|docx|jpe?g|png|webp)$/i;

export default function HoaCaseEvidencePanel({
  associationId, propertyId, caseId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const [links, setLinks] = useState<Evidence[]>([]);
  const [documents, setDocuments] = useState<EntityAttachment[]>([]);
  const [attachmentId, setAttachmentId] = useState("");
  const [kind, setKind] = useState<Evidence["evidence_type"]>("PHOTO");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = "/api/hoa/associations/" + associationId +
    "/staff-cases/" + caseId + "/evidence";
  const query = "?property_id=" + propertyId;

  async function reload() {
    const [refs, stored] = await Promise.all([
      apiGet(base + query) as Promise<Evidence[]>,
      listEntityAttachments("properties", propertyId),
    ]);
    setLinks(refs);
    setDocuments(stored.items.filter((doc) =>
      !doc.share_with_tenants && !doc.share_with_owners
      && SUPPORTED.test(doc.original_name)
    ));
  }

  useEffect(() => {
    let alive = true;
    void Promise.all([
      apiGet(base + query) as Promise<Evidence[]>,
      listEntityAttachments("properties", propertyId),
    ]).then(([refs, stored]) => {
      if (!alive) return;
      setLinks(refs);
      setDocuments(stored.items.filter((doc) =>
        !doc.share_with_tenants && !doc.share_with_owners
        && SUPPORTED.test(doc.original_name)
      ));
    }).catch((cause) => {
      if (alive) setError(cause instanceof Error ? cause.message : "Private case evidence unavailable.");
    });
    return () => { alive = false; };
  }, [base, query, propertyId]);

  async function link() {
    if (!canEdit || busy || !attachmentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId,
        attachment_id: Number(attachmentId), evidence_type: kind,
      });
      setAttachmentId("");
      await reload();
      setMessage("Private case evidence linked. This is not a legal finding or notice.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot link private case evidence.");
    } finally { setBusy(false); }
  }

  async function unlink(linkId: number) {
    if (!canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + linkId + query);
      await reload();
      setMessage("Case evidence reference archived. Source file was not deleted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot archive case evidence.");
    } finally { setBusy(false); }
  }

  const available = documents.filter(
    (doc) => !links.some((link) => link.attachment_id === doc.id)
  );

  return (
    <section className="space-y-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-semibold">Private violation evidence · case #{caseId}</h4>
        <button type="button" onClick={onClose} className="text-blue-700">Close evidence</button>
      </div>
      <p className="text-xs text-amber-900">
        References existing private property documents or photos. A file does
        not establish that a violation occurred, prove service of notice,
        authorize a penalty, or become visible to a member. Upload private
        files using the property's existing attachment uploader first.
      </p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-emerald-700">{message}</p>}
      {links.length === 0 && <p className="text-xs">No private evidence linked.</p>}
      <ol className="space-y-2">
        {links.map((link) => (
          <li key={link.id} className="flex flex-wrap items-center gap-2 rounded border bg-white p-2">
            <span className="flex-1 break-all">
              {link.evidence_type} · {link.filename}
            </span>
            <button type="button" disabled={busy}
              onClick={() => {
                void downloadEntityAttachment(link.attachment_id, link.filename)
                  .catch((cause) => {
                    setError(cause instanceof Error ? cause.message : "Unable to download private evidence.");
                  });
              }} className="text-blue-700 disabled:opacity-50">
              Download private evidence
            </button>
            {canEdit && (
              <button type="button" disabled={busy}
                onClick={() => { void unlink(link.id); }}
                className="text-red-700 disabled:opacity-50">
                Archive link
              </button>
            )}
          </li>
        ))}
      </ol>
      {canEdit && (
        <div className="space-y-2 border-t pt-2">
          <label className="block text-xs">Private property evidence file
            <select aria-label="Private property evidence file" value={attachmentId}
              onChange={(event) => setAttachmentId(event.target.value)}
              className="mt-1 block w-full rounded border bg-white p-2 text-sm">
              <option value="">Select previously uploaded private file</option>
              {available.map((item) => (
                <option key={item.id} value={item.id}>{item.original_name}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs">Evidence category
            <select aria-label="Evidence category" value={kind}
              onChange={(event) => setKind(event.target.value as Evidence["evidence_type"])}
              className="mt-1 block rounded border bg-white p-2 text-sm">
              <option value="PHOTO">Photo</option>
              <option value="DOCUMENT">Document</option>
              <option value="OTHER">Other</option>
            </select>
          </label>
          <button type="button" disabled={!attachmentId || busy}
            onClick={() => { void link(); }}
            className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
            Link private case evidence
          </button>
        </div>
      )}
    </section>
  );
}
