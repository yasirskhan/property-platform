"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ReportActions from "@/components/reporting/ReportActions";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Property = { id: number; name: string; is_active: boolean };
type Group = {
  id: number; name: string; description: string | null;
  property_ids: number[]; updated_at: string;
};
type Preview = { title: string; headers: string[]; rows: (string | number)[][]; total: number };
type Viewer = { role: string };
const KEY = "property.group_directory";

export default function PropertyGroupsPage() {
  const [role, setRole] = useState("");
  const [properties, setProperties] = useState<Property[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [members, setMembers] = useState<number[]>([]);
  const [editId, setEditId] = useState<number | null>(null);
  const [groupFilter, setGroupFilter] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function start() {
      try {
        const me = await apiGet("/auth/me") as Viewer;
        if (!active) return;
        setRole(me.role);
        const [listing, locations] = await Promise.all([
          apiGet("/api/property-groups") as Promise<Group[]>,
          apiGet("/properties") as Promise<Property[]>,
        ]);
        if (!active) return;
        setGroups(listing);
        setProperties(locations.filter((p) => p.is_active));
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Property groups unavailable.");
      } finally { if (active) setLoading(false); }
    }
    void start();
    return () => { active = false; };
  }, []);

  function clearForm() {
    setEditId(null); setName(""); setDescription(""); setMembers([]);
  }

  function edit(item: Group) {
    setEditId(item.id); setName(item.name);
    setDescription(item.description || ""); setMembers([...item.property_ids]);
    setError(""); setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const payload = { name: name.trim(), description: description.trim() || null, property_ids: members };
      const saved = editId === null
        ? await apiPost("/api/property-groups", payload) as Group
        : await apiPut("/api/property-groups/" + editId, payload) as Group;
      setGroups((old) => [saved, ...old.filter((x) => x.id !== saved.id)]);
      clearForm();
      setPreview(null); setApplied({});
      setMessage("Named group and explicit memberships saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save group.");
    } finally { setBusy(false); }
  }

  async function remove(id: number) {
    if (!window.confirm("Delete this named group and its memberships?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete("/api/property-groups/" + id);
      setGroups((old) => old.filter((x) => x.id !== id));
      if (editId === id) clearForm();
      setPreview(null); setApplied({}); setGroupFilter("");
      setMessage("Group deleted. Underlying properties were not deleted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to delete group.");
    } finally { setBusy(false); }
  }

  async function loadReport() {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const params = groupFilter ? { group_id: groupFilter } : {};
    const q = new URLSearchParams(params).toString();
    try {
      const data = await apiGet("/api/reporting/property-groups/preview" + (q ? "?" + q : "")) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Group directory unavailable.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Property Group Directory</h1>
        <p className="mt-1 text-sm text-slate-600">
          Only explicitly maintained named group memberships are reported.
          A manager sees only groups containing their assigned properties,
          not other members of those groups.
        </p>
      </header>
      {loading && <p className="text-sm text-slate-500">Loading property groups…</p>}
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded-lg border border-green-200 p-3 text-sm text-green-700">{message}</p>}
      {!loading && role === "ADMIN" && (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="font-semibold">Manage named property groups</h2>
          <p className="my-2 text-sm text-slate-500">
            Group names are manual. Adding a property does not grant access
            to its staff or change any property ownership.
          </p>
          <form onSubmit={(event) => { event.preventDefault(); void save(event); }} className="space-y-3">
            <label className="block text-sm">Name
              <input required maxLength={100} value={name}
                onChange={(event) => setName(event.target.value)}
                className="mt-1 block w-full max-w-md rounded border p-2" />
            </label>
            <label className="block text-sm">Description (optional)
              <input maxLength={500} value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="mt-1 block w-full max-w-lg rounded border p-2" />
            </label>
            <fieldset className="max-h-48 overflow-auto rounded border p-3">
              <legend className="text-sm font-semibold">Explicit property members</legend>
              {properties.map((prop) => (
                <label key={prop.id} className="flex items-center gap-2 py-1 text-sm">
                  <input type="checkbox" checked={members.includes(prop.id)}
                    onChange={(event) => setMembers((old) => event.target.checked
                      ? [...old, prop.id] : old.filter((id) => id !== prop.id))} />
                  {prop.name} (#{prop.id})
                </label>
              ))}
              {properties.length === 0 && <p className="text-sm text-slate-500">No active properties.</p>}
            </fieldset>
            <div className="flex gap-2">
              <button type="submit" disabled={busy || !name.trim()}
                className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                {busy ? "Saving…" : editId === null ? "Create group" : "Update group"}
              </button>
              {editId !== null && <button type="button" onClick={clearForm}
                className="rounded border px-4 py-2 text-sm">Cancel edit</button>}
            </div>
          </form>
        </section>
      )}
      {!loading && (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="font-semibold">Recorded groups</h2>
          {groups.length === 0 && <p className="mt-2 text-sm text-slate-500">No named groups currently available.</p>}
          {groups.map((group) => (
            <div key={group.id} className="flex flex-wrap items-center justify-between gap-3 border-b py-3 text-sm">
              <div>
                <strong>{group.name}</strong>
                <p className="text-slate-600">
                  {group.property_ids.length} visible member propert{group.property_ids.length === 1 ? "y" : "ies"}
                </p>
              </div>
              {role === "ADMIN" && <div className="flex gap-2">
                <button type="button" disabled={busy} onClick={() => edit(group)}
                  className="rounded border px-3 py-1.5">Edit</button>
                <button type="button" disabled={busy} onClick={() => void remove(group.id)}
                  className="rounded border px-3 py-1.5 text-red-700">Delete</button>
              </div>}
            </div>
          ))}
        </section>
      )}
      {!loading && (
        <section className="space-y-3">
          <form onSubmit={(event) => { event.preventDefault(); void loadReport(); }}
            className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
            <label className="text-sm">Group
              <select value={groupFilter} onChange={(event) => { setGroupFilter(event.target.value); setPreview(null); setApplied({}); }}
                className="mt-1 block rounded border p-2">
                <option value="">All visible groups</option>
                {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            </label>
            <button type="submit" disabled={busy}
              className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Loading…" : "Load group directory"}
            </button>
          </form>
          {preview && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <span><strong>{preview.total}</strong> group/member rows.</span>
                <ReportActions reportKey={KEY} parameters={applied} />
              </div>
              <div className="overflow-x-auto rounded-xl border bg-white">
                <table className="min-w-[1000px] w-full text-sm">
                  <thead className="bg-slate-50"><tr>{preview.headers.map((h) => (
                    <th key={h} scope="col" className="px-3 py-2 text-left font-semibold">{h}</th>
                  ))}</tr></thead>
                  <tbody>{preview.rows.map((row, index) => (
                    <tr key={index} className="border-t">{row.map((v, i) => (
                      <td key={i} className="px-3 py-2">{String(v)}</td>
                    ))}</tr>
                  ))}{preview.total === 0 && (
                    <tr><td colSpan={preview.headers.length} className="p-5 text-center text-slate-500">
                      No recorded matching property group memberships.
                    </td></tr>
                  )}</tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}
