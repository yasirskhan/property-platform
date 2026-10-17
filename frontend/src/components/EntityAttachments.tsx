"use client";

import { useEffect, useState } from "react";
import {
  deleteEntityAttachment,
  downloadEntityAttachment,
  EntityAttachment,
  listEntityAttachments,
  updateAttachmentSharing,
  uploadEntityAttachment,
} from "@/lib/entityAttachments";
import { formatDate } from "@/lib/money";

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function EntityAttachments({
  entityType,
  entityId,
  canManage = true,
}: {
  entityType: string;
  entityId: number;
  canManage?: boolean;
}) {
  const [items, setItems] = useState<EntityAttachment[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [shareWithTenants, setShareWithTenants] = useState(false);
  const [shareWithOwners, setShareWithOwners] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listEntityAttachments(entityType, entityId);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load attachments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityType, entityId]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setSaving(true);
    setError("");
    try {
      await uploadEntityAttachment(entityType, entityId, file, shareWithTenants, shareWithOwners);
      setFile(null);
      setShareWithTenants(false);
      setShareWithOwners(false);
      const input = document.getElementById("entity-attachment-file") as HTMLInputElement | null;
      if (input) input.value = "";
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload attachment");
    } finally {
      setSaving(false);
    }
  }

  async function toggleSharing(item: EntityAttachment, field: "share_with_tenants" | "share_with_owners") {
    setError("");
    try {
      const updated = await updateAttachmentSharing(item.id, { [field]: !item[field] });
      setItems((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update sharing");
    }
  }

  async function remove(item: EntityAttachment) {
    if (!confirm(`Remove attachment "${item.original_name}"?`)) return;
    setError("");
    try {
      await deleteEntityAttachment(item.id);
      setItems((current) => current.filter((row) => row.id !== item.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove attachment");
    }
  }

  if (loading) return <div className="text-slate-500">Loading attachments…</div>;

  return (
    <div className="space-y-4">
      {error && <div className="px-4 py-2 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">{error}</div>}
      {canManage && (
        <form onSubmit={submit} className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Add attachment</label>
            <input
              id="entity-attachment-file"
              type="file"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              className="block w-full text-sm text-slate-700"
            />
            <p className="text-xs text-slate-500 mt-1">Images, PDF, Word, Excel, and CSV up to 10 MB.</p>
          </div>
          <div className="flex flex-wrap gap-5 text-sm text-slate-700">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={shareWithTenants} onChange={(event) => setShareWithTenants(event.target.checked)} />
              Share with tenants
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={shareWithOwners} onChange={(event) => setShareWithOwners(event.target.checked)} />
              Share with owners
            </label>
          </div>
          <button type="submit" disabled={!file || saving} className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium disabled:opacity-50">
            {saving ? "Uploading…" : "Upload"}
          </button>
        </form>
      )}
      {items.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-sm text-slate-500">No attachments yet.</div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100">
          {items.map((item) => (
            <div key={item.id} className="p-5 flex flex-wrap items-center justify-between gap-4">
              <div className="min-w-0">
                <button type="button" onClick={() => downloadEntityAttachment(item.id, item.original_name)} className="font-medium text-slate-900 hover:underline break-all text-left">
                  {item.original_name}
                </button>
                <div className="text-xs text-slate-500 mt-1">
                  {formatSize(item.size_bytes)} · {item.uploaded_by_name || "Unknown user"} · {formatDate(item.created_at)}
                </div>
                <div className="flex flex-wrap gap-3 mt-2 text-xs text-slate-600">
                  <span>{item.share_with_tenants ? "Shared with tenants" : "Internal for tenants"}</span>
                  <span>{item.share_with_owners ? "Shared with owners" : "Internal for owners"}</span>
                </div>
              </div>
              {canManage && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => toggleSharing(item, "share_with_tenants")} className="text-xs px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50">
                    {item.share_with_tenants ? "Unshare tenants" : "Share tenants"}
                  </button>
                  <button type="button" onClick={() => toggleSharing(item, "share_with_owners")} className="text-xs px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50">
                    {item.share_with_owners ? "Unshare owners" : "Share owners"}
                  </button>
                  <button type="button" onClick={() => remove(item)} className="text-xs px-3 py-1.5 border border-red-200 text-red-700 rounded-lg hover:bg-red-50">
                    Remove
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
