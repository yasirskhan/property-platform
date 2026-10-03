"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";

type Tag = { id: number; name: string; is_active: boolean };
type TagList = { items: Tag[]; total: number };

export default function TagPicker({
  entityType, entityId, canCreate = false,
}: {
  entityType: "contacts" | "vendors" | "work_orders" | "properties" | "units" | "leases" | "bills";
  entityId: number; canCreate?: boolean;
}) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [assigned, setAssigned] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const targetPath = `/api/tags/target/${encodeURIComponent(entityType)}/${entityId}`;

  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setAssigned([]); setSelected("");
    Promise.all([
      apiGet("/api/tags") as Promise<TagList>,
      apiGet(targetPath) as Promise<TagList>,
    ]).then(([vocabulary, current]) => {
      if (active) { setTags(vocabulary.items); setAssigned(current.items); }
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Tags unavailable.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [targetPath]);

  async function apply() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const result = await apiPost(`${targetPath}/${selected}`) as Tag;
      setAssigned((prior) => prior.some((row) => row.id === result.id) ? prior : [...prior,result]);
      setSelected("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not link tag.");
    } finally { setBusy(false); }
  }

  async function remove(tagId: number) {
    setBusy(true); setError("");
    try {
      await apiDelete(`${targetPath}/${tagId}`);
      setAssigned((prior) => prior.filter((item) => item.id !== tagId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove tag.");
    } finally { setBusy(false); }
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true); setError("");
    try {
      const created = await apiPost("/api/tags", {name:name.trim()}) as Tag;
      setTags((prior) => [...prior, created].sort((a,b) => a.name.localeCompare(b.name)));
      setName("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create tag.");
    } finally { setBusy(false); }
  }

  const available = tags.filter((tag) => tag.is_active && !assigned.some((current) => current.id === tag.id));

  return (
    <section className="rounded-xl border bg-white p-4" aria-label={`Tags for ${entityType} #${entityId}`}>
      <h3 className="font-semibold">Tags</h3>
      <p className="mt-1 text-xs text-slate-500">
        Organization labels on this record only. Tags do not change accounting, assignments or permissions.
      </p>
      {loading && <p className="mt-2 text-sm text-slate-500">Loading tags…</p>}
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {!loading && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            {assigned.map((tag) => (
              <span key={tag.id} className="inline-flex items-center gap-2 rounded-full border bg-slate-50 px-3 py-1 text-sm">
                {tag.name}{!tag.is_active && " (archived)"}
                <button disabled={busy} type="button" onClick={() => { void remove(tag.id); }}
                  aria-label={`Remove ${tag.name}`} className="text-red-700 disabled:opacity-50">×</button>
              </span>
            ))}
            {assigned.length === 0 && <span className="text-sm text-slate-500">No tags assigned.</span>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select value={selected} disabled={busy || available.length === 0}
              aria-label="Available organization tags"
              onChange={(event) => setSelected(event.target.value)}
              className="rounded border px-3 py-2 text-sm">
              <option value="">Choose an existing tag</option>
              {available.map((tag) => <option value={tag.id} key={tag.id}>{tag.name}</option>)}
            </select>
            <button type="button" disabled={busy || !selected} onClick={() => { void apply(); }}
              className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">Add tag</button>
          </div>
          {canCreate && <form onSubmit={(event) => { void create(event); }} className="flex flex-wrap items-center gap-2">
            <input value={name} maxLength={50} aria-label="New tag name"
              onChange={(event) => setName(event.target.value)}
              placeholder="New organization tag" className="rounded border px-3 py-2 text-sm" />
            <button type="submit" disabled={busy || !name.trim()}
              className="rounded border px-3 py-2 text-sm disabled:opacity-50">Create tag</button>
          </form>}
        </div>
      )}
    </section>
  );
}
