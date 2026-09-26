"use client";

import { useEffect, useState } from "react";
import { addEntityNote, EntityNote, listEntityNotes } from "@/lib/entityNotes";
import { formatDate } from "@/lib/money";

export default function EntityNotes({
  entityType,
  entityId,
  canAdd = true,
}: {
  entityType: string;
  entityId: number;
  canAdd?: boolean;
}) {
  const [items, setItems] = useState<EntityNote[]>([]);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listEntityNotes(entityType, entityId);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load notes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityType, entityId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const clean = body.trim();
    if (!clean) return;
    setSaving(true);
    setError("");
    try {
      await addEntityNote(entityType, entityId, clean);
      setBody("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add note");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading notes…</div>;

  return (
    <div className="space-y-4">
      {error && (
        <div className="px-4 py-2 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">
          {error}
        </div>
      )}

      {canAdd && (
        <form onSubmit={submit} className="bg-white border border-slate-200 rounded-xl p-5">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Add note
          </label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            maxLength={10000}
            placeholder="Add an internal note..."
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
          />
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={saving || !body.trim()}
              className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium disabled:opacity-50"
            >
              {saving ? "Adding…" : "Add Note"}
            </button>
          </div>
        </form>
      )}

      {items.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-sm text-slate-500">
          No notes yet.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((note) => (
            <div key={note.id} className="bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-center justify-between gap-4 mb-2 text-xs text-slate-500">
                <span>{note.created_by_name || "Unknown user"}</span>
                <span>{formatDate(note.created_at)}</span>
              </div>
              <p className="text-sm text-slate-800 whitespace-pre-wrap">{note.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
