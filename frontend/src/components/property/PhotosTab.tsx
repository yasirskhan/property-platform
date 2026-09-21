// ============================================================
// PhotosTab.tsx
// ------------------------------------------------------------
// Property photos grid with:
//   * Multi-file upload (bulk)
//   * Cover flag (only one per property)
//   * Marketing flag (for listings)
//   * Captions (edit inline)
//   * Delete with styled confirm modal
// ============================================================

"use client";

import { useEffect, useRef, useState } from "react";
import {
  listPhotos,
  createPhoto,
  updatePhoto,
  deletePhoto,
  PropertyPhoto,
} from "@/lib/propertyPhotos";
import { apiUpload, fileUrl } from "@/lib/api";

export default function PhotosTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [items, setItems] = useState<PropertyPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadCount, setUploadCount] = useState(0);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Edit-in-modal state
  const [editing, setEditing] = useState<PropertyPhoto | null>(null);
  const [editCaption, setEditCaption] = useState("");
  const [editMarketing, setEditMarketing] = useState(false);
  const [editCover, setEditCover] = useState(false);

  // Confirm delete
  const [confirmingDelete, setConfirmingDelete] =
    useState<PropertyPhoto | null>(null);

  // Lightbox (click a photo to see it big)
  const [lightbox, setLightbox] = useState<PropertyPhoto | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listPhotos(propertyId, false);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  // ------------------------------------------------------------
  // Bulk upload
  // ------------------------------------------------------------
  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadCount(files.length);
    setError("");
    let ok = 0;
    try {
      for (const file of Array.from(files)) {
        // 1. Upload the raw file
        const uploaded = await apiUpload(file);

        // 2. Create the photo record
        await createPhoto(propertyId, {
          url: uploaded.url,
          filename: uploaded.filename,
          original_name: uploaded.original_name,
          content_type: uploaded.content_type,
          size_bytes: uploaded.size,
          caption: null,
          is_marketing: false,
          is_cover: false,
        });
        ok += 1;
      }
      await load();
    } catch (err) {
      setError(
        err instanceof Error
          ? `Uploaded ${ok} of ${files.length}. Error: ${err.message}`
          : "Upload failed"
      );
    } finally {
      setUploading(false);
      setUploadCount(0);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  // ------------------------------------------------------------
  // Edit
  // ------------------------------------------------------------
  function openEdit(p: PropertyPhoto) {
    setEditing(p);
    setEditCaption(p.caption || "");
    setEditMarketing(p.is_marketing);
    setEditCover(p.is_cover);
  }

  async function saveEdit() {
    if (!editing) return;
    setWorking(true);
    setError("");
    try {
      await updatePhoto(propertyId, editing.id, {
        caption: editCaption || null,
        is_marketing: editMarketing,
        is_cover: editCover,
      });
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setWorking(false);
    }
  }

  // ------------------------------------------------------------
  // Quick toggles
  // ------------------------------------------------------------
  async function setAsCover(p: PropertyPhoto) {
    setWorking(true);
    setError("");
    try {
      await updatePhoto(propertyId, p.id, { is_cover: true });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set cover");
    } finally {
      setWorking(false);
    }
  }

  async function toggleMarketing(p: PropertyPhoto) {
    setWorking(true);
    setError("");
    try {
      await updatePhoto(propertyId, p.id, {
        is_marketing: !p.is_marketing,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setWorking(false);
    }
  }

  // ------------------------------------------------------------
  // Delete
  // ------------------------------------------------------------
  function askDelete(p: PropertyPhoto) {
    setConfirmingDelete(p);
  }

  async function reallyDelete(p: PropertyPhoto) {
    setWorking(true);
    setError("");
    try {
      await deletePhoto(propertyId, p.id);
      setConfirmingDelete(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div>
      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Toolbar */}
      {canEdit && (
        <div className="mb-6 flex items-center justify-between">
          <div className="text-sm text-slate-600">
            {items.length} photo{items.length === 1 ? "" : "s"}
            {" · "}
            <span className="text-slate-500">
              Cover:{" "}
              {items.find((p) => p.is_cover)?.caption ||
                (items.find((p) => p.is_cover)
                  ? `#${items.find((p) => p.is_cover)!.id}`
                  : "none")}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
            <button
              onClick={openFilePicker}
              disabled={uploading}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              {uploading
                ? `Uploading ${uploadCount}…`
                : "+ Upload Photos"}
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {items.length === 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-500 text-sm">
          No photos yet.
          {canEdit && (
            <div className="mt-3">
              <button
                onClick={openFilePicker}
                className="text-blue-600 hover:underline text-sm"
              >
                Upload your first photo
              </button>
            </div>
          )}
        </div>
      )}

      {/* Grid */}
      {items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((p) => (
            <div
              key={p.id}
              className="group relative bg-white border border-slate-200 rounded-xl overflow-hidden"
            >
              {/* Thumbnail */}
              <button
                onClick={() => setLightbox(p)}
                className="block w-full aspect-video bg-slate-100 hover:opacity-90"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={fileUrl(p.url)}
                  alt={p.caption || p.original_name || "Property photo"}
                  className="w-full h-full object-cover"
                />
              </button>

              {/* Badges */}
              <div className="absolute top-2 left-2 flex flex-col gap-1">
                {p.is_cover && (
                  <span className="text-xs px-2 py-0.5 bg-amber-500 text-white rounded-full shadow">
                    ★ Cover
                  </span>
                )}
                {p.is_marketing && (
                  <span className="text-xs px-2 py-0.5 bg-blue-600 text-white rounded-full shadow">
                    Marketing
                  </span>
                )}
              </div>

              {/* Caption + actions */}
              <div className="p-3">
                <div className="text-xs text-slate-700 truncate mb-2">
                  {p.caption || (
                    <span className="text-slate-400 italic">
                      (no caption)
                    </span>
                  )}
                </div>

                {canEdit && (
                  <div className="flex flex-wrap gap-2 text-xs">
                    <button
                      onClick={() => openEdit(p)}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                    {!p.is_cover && (
                      <button
                        onClick={() => setAsCover(p)}
                        disabled={working}
                        className="text-amber-700 hover:text-amber-900 disabled:opacity-50"
                      >
                        Set cover
                      </button>
                    )}
                    <button
                      onClick={() => toggleMarketing(p)}
                      disabled={working}
                      className="text-slate-600 hover:text-slate-900 disabled:opacity-50"
                    >
                      {p.is_marketing ? "Unmarket" : "Mark marketing"}
                    </button>
                    <button
                      onClick={() => askDelete(p)}
                      className="text-red-600 hover:text-red-800 ml-auto"
                    >
                      Remove
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <>
          <div
            className="fixed inset-0 bg-black/80 z-40"
            onClick={() => setLightbox(null)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-6 pointer-events-none">
            <div className="pointer-events-auto max-w-5xl max-h-[90vh] flex flex-col items-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={fileUrl(lightbox.url)}
                alt={lightbox.caption || lightbox.original_name || ""}
                className="max-h-[80vh] max-w-full rounded-lg shadow-2xl"
              />
              {(lightbox.caption || lightbox.original_name) && (
                <div className="mt-3 text-white text-sm text-center">
                  {lightbox.caption || lightbox.original_name}
                </div>
              )}
              <button
                onClick={() => setLightbox(null)}
                className="mt-4 text-white text-sm underline"
              >
                Close
              </button>
            </div>
          </div>
        </>
      )}

      {/* Edit modal */}
      {editing && (
        <>
          <div
            className="fixed inset-0 bg-black/40 z-40"
            onClick={() => !working && setEditing(null)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <div className="w-full max-w-md bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
              <div className="px-6 py-4 border-b border-slate-200">
                <div className="font-semibold text-slate-900 text-lg">
                  Edit Photo
                </div>
              </div>

              <div className="p-6 space-y-4 text-sm">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">
                    Caption
                  </label>
                  <input
                    type="text"
                    value={editCaption}
                    onChange={(e) => setEditCaption(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                  />
                </div>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={editMarketing}
                    onChange={(e) => setEditMarketing(e.target.checked)}
                  />
                  <span className="text-slate-700">
                    Show in marketing / listings
                  </span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={editCover}
                    onChange={(e) => setEditCover(e.target.checked)}
                  />
                  <span className="text-slate-700">
                    Make this the cover photo
                  </span>
                </label>
              </div>

              <div className="border-t border-slate-200 p-4 flex items-center justify-end gap-3">
                <button
                  onClick={() => setEditing(null)}
                  disabled={working}
                  className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
                >
                  Cancel
                </button>
                <button
                  onClick={saveEdit}
                  disabled={working}
                  className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
                >
                  {working ? "Saving…" : "Save"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Confirm delete modal */}
      {confirmingDelete && (
        <>
          <div
            className="fixed inset-0 bg-black/40 z-40"
            onClick={() => !working && setConfirmingDelete(null)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <div className="w-full max-w-md bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
              <div className="px-6 py-4 border-b border-slate-200">
                <div className="font-semibold text-slate-900 text-lg">
                  Remove photo?
                </div>
              </div>
              <div className="px-6 py-5 text-sm text-slate-700">
                {confirmingDelete.caption
                  ? `Remove "${confirmingDelete.caption}"?`
                  : "Remove this photo from the property?"}
              </div>
              <div className="border-t border-slate-200 p-4 flex items-center justify-end gap-3">
                <button
                  onClick={() => setConfirmingDelete(null)}
                  disabled={working}
                  className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
                >
                  Cancel
                </button>
                <button
                  onClick={() => reallyDelete(confirmingDelete)}
                  disabled={working}
                  className="text-sm px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {working ? "Removing…" : "Remove"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}