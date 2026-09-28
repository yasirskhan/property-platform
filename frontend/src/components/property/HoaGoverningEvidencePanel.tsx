"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import EntityAttachments from "@/components/EntityAttachments";
import { downloadEntityAttachment, listEntityAttachments, type EntityAttachment } from "@/lib/entityAttachments";

type Evidence = {
  id: number;
  association_id: number;
  property_id: number;
  attachment_id: number;
  evidence_type: string;
  filename: string;
  recorded_at: string;
  status: "STAFF_SUPPLIED_UNVERIFIED";
};

const CATEGORIES: { key: string; label: string }[] = [
  { key: "DECLARATION", label: "Declaration" },
  { key: "BYLAWS", label: "Bylaws" },
  { key: "COVENANTS", label: "Covenants" },
  { key: "RULES", label: "Rules and regulations" },
  { key: "ARC_GUIDELINES", label: "ARC guidelines" },
  { key: "RESERVE_STUDY", label: "Reserve study" },
  { key: "OTHER", label: "Other document" },
];

function privateDocument(row: EntityAttachment) {
  return !row.share_with_tenants && !row.share_with_owners
    && /\.(pdf|doc|docx)$/i.test(row.original_name);
}

export default function HoaGoverningEvidencePanel({ associationId, propertyId, canEdit, onClose }: {
  associationId: number; propertyId: number; canEdit: boolean; onClose: () => void;
}) {
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [attachments, setAttachments] = useState<EntityAttachment[]>([]);
  const [attachmentId, setAttachmentId] = useState("");
  const [category, setCategory] = useState("DECLARATION");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const base = "/api/hoa/associations/" + associationId + "/governing-evidence";
  const query = "?property_id=" + propertyId;

  async function reload() {
    const [links, stored] = await Promise.all([
      apiGet(base + query) as Promise<Evidence[]>,
      listEntityAttachments("properties", propertyId),
    ]);
    setEvidence(links);
    setAttachments(stored.items.filter(privateDocument));
  }

  useEffect(() => {
    let active = true;
    setError(""); setMessage(""); setLoading(true);
    void Promise.all([
      apiGet(base + query) as Promise<Evidence[]>,
      listEntityAttachments("properties", propertyId),
    ]).then(([links, stored]) => {
      if (!active) return;
      setEvidence(links);
      setAttachments(stored.items.filter(privateDocument));
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Governing-document evidence unavailable.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, query, propertyId]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !attachmentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId, attachment_id: Number(attachmentId),
        evidence_type: category,
      });
      setAttachmentId("");
      await reload();
      setMessage("Staff evidence reference recorded. Document authority remains unverified.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to link evidence.");
    } finally { setBusy(false); }
  }

  async function archive(row: Evidence) {
    if (!canEdit || busy || !window.confirm("Archive this staff evidence reference? The original property file is retained.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + row.id + query);
      setEvidence((prior) => prior.filter((item) => item.id !== row.id));
      setMessage("Reference archived; no legal action or accounting change occurred.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive reference.");
    } finally { setBusy(false); }
  }

  return (
    <section className="w-full space-y-3 rounded-lg border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Governing document evidence</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-600">
        This is a staff-supplied document index, not verification of governing authority,
        jurisdiction, applicable law, dues liability, board approval or reserve accounting.
        Documents must be reviewed by an authorized decision-maker before any formal action.
        Files stay in existing property attachments. No fines, notices, approvals or GL entries are created.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading evidence…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && evidence.length === 0 && (
        <p className="text-sm text-slate-500">No governing documents have been indexed for this property.</p>
      )}
      {!loading && evidence.map((row) => (
        <div key={row.id} className="flex flex-wrap items-start justify-between gap-2 rounded border bg-white p-3">
          <div className="min-w-0 text-sm">
            <p className="font-medium break-all">{row.filename}</p>
            <p className="text-xs text-slate-600">
              {CATEGORIES.find((item) => item.key === row.evidence_type)?.label || row.evidence_type}
              {" · "}STAFF-SUPPLIED / UNVERIFIED
            </p>
          </div>
          <div className="flex gap-3 text-sm">
            <button type="button" onClick={() => {
              void downloadEntityAttachment(row.attachment_id, row.filename).catch((cause) =>
                setError(cause instanceof Error ? cause.message : "Document download unavailable.")
              );
            }} className="text-blue-700">Download</button>
            {canEdit && <button type="button" disabled={busy}
              onClick={() => { void archive(row); }} className="text-red-700 disabled:opacity-50">Archive link</button>}
          </div>
        </div>
      ))}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-3 border-t pt-3">
          <h4 className="text-sm font-semibold">Link existing private property document</h4>
          <p className="text-xs text-slate-600">
            Select an unshared PDF or Word document. Linked source files cannot be shared with
            tenants or owners using the generic attachment controls. Use the existing upload
            below to add a file without enabling sharing.
          </p>
          <label className="block text-sm">Document
            <select required value={attachmentId} onChange={(event) => setAttachmentId(event.target.value)}
              className="mt-1 block w-full rounded border p-2">
              <option value="">Select a private property document</option>
              {attachments.map((item) => (
                <option key={item.id} value={item.id}>{item.original_name} (#{item.id})</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">Staff-supplied document category
            <select value={category} onChange={(event) => setCategory(event.target.value)}
              className="mt-1 block w-full rounded border p-2">
              {CATEGORIES.map((item) => (
                <option key={item.key} value={item.key}>{item.label}</option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-3 text-sm">
            <button type="submit" disabled={busy || !attachmentId}
              className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
              {busy ? "Saving…" : "Record evidence reference"}
            </button>
            <button type="button" disabled={busy} onClick={() => {
              void reload().catch((cause) => setError(cause instanceof Error ? cause.message : "Refresh unavailable."));
            }} className="rounded border px-3 py-2">Refresh files</button>
            <button type="button" onClick={() => setShowUpload((old) => !old)}
              className="rounded border px-3 py-2">{showUpload ? "Hide property upload" : "Upload private file"}</button>
          </div>
        </form>
      )}
      {canEdit && !loading && showUpload && (
        <EntityAttachments entityType="properties" entityId={propertyId} canManage />
      )}
    </section>
  );
}
