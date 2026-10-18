"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

type UnitChoice = { id: number; unit_number: string; property_id: number; property_name: string };
const CATEGORIES = ["plumbing", "electrical", "hvac", "appliance", "general", "pest", "cleaning", "landscaping", "other"];
const PRIORITIES = ["low", "medium", "high", "emergency"];

export default function NewMaintenanceRequest() {
  const router = useRouter();
  const [units, setUnits] = useState<UnitChoice[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("other");
  const [priority, setPriority] = useState("medium");
  const [permission, setPermission] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    if (appliedSearch) params.set("search", appliedSearch);
    apiGet("/work-orders/request-units?" + params.toString())
      .then((value: UnitChoice[]) => {
        if (!active) return;
        if (!Array.isArray(value)) throw new Error("Unexpected unit list.");
        setUnits(value);
        setSelectedId((prev) => value.some((u) => String(u.id) === prev) ? prev : "");
      })
      .catch((cause) => {
        if (active) {
          setUnits([]);
          setSelectedId("");
          setError(cause instanceof Error ? cause.message : "Units unavailable.");
        }
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, appliedSearch]);

  function findUnits(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedSearch(search.trim());
    setOffset(0);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const unitId = Number(selectedId);
    if (!units.some((u) => u.id === unitId) || !Number.isSafeInteger(unitId)) {
      setError("Select a unit you are authorized to access.");
      return;
    }
    if (title.trim().length < 3 || description.trim().length < 10) {
      setError("Enter a title of at least 3 characters and a description of at least 10.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await apiPost("/work-orders", {
        unit_id: unitId, title: title.trim(), description: description.trim(),
        category, priority, permission_to_enter: permission,
      }) as { id: number };
      if (!Number.isSafeInteger(result.id) || result.id < 1) throw new Error("Invalid saved request.");
      router.push("/dashboard/maintenance/work-orders/" + result.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Maintenance request could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link href="/dashboard/maintenance/work-orders" className="text-sm text-blue-700 hover:underline">
        Back to work orders
      </Link>
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">New maintenance request</h1>
        <p className="mt-1 text-sm text-slate-600">
          Select a unit in your authorized properties or active lease. Your request will be recorded for staff review.
        </p>
      </header>
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-800">{error}</p>}
      <form onSubmit={findUnits} className="rounded-xl border bg-white p-4">
        <label className="text-sm">Find property or unit
          <input aria-label="Find property or unit" maxLength={80} value={search}
            onChange={(event) => setSearch(event.target.value)} className="mt-1 w-full rounded-lg border p-2"
            placeholder="Property name or unit number" />
        </label>
        <button type="submit" disabled={loading} className="mt-3 rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
          Search units
        </button>
      </form>
      <form onSubmit={(event) => void submit(event)} className="space-y-4 rounded-xl border bg-white p-5">
        <label className="block text-sm">Unit
          <select aria-label="Maintenance request unit" required className="mt-1 w-full rounded-lg border p-2"
            disabled={loading || saving} value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}>
            <option value="">Choose an authorized unit</option>
            {units.map((u) => <option key={u.id} value={u.id}>{u.property_name} · Unit {u.unit_number}</option>)}
          </select>
        </label>
        <div className="flex justify-between gap-2 text-xs text-slate-600">
          <button type="button" onClick={() => setOffset((v) => Math.max(0, v - 50))}
            disabled={loading || offset === 0} className="rounded-lg border px-3 py-2 disabled:opacity-40">Previous units</button>
          <span>Units page {Math.floor(offset / 50) + 1}{loading ? " · Loading" : ""}</span>
          <button type="button" disabled={loading || units.length < 50} onClick={() => setOffset((v) => v + 50)}
            className="rounded-lg border px-3 py-2 disabled:opacity-40">Next units</button>
        </div>
        {!loading && units.length === 0 && <p className="text-sm text-slate-600">No eligible units found. Only active leases or assigned properties can submit requests.</p>}
        <label className="block text-sm">Problem title
          <input required minLength={3} maxLength={255} aria-label="Maintenance problem title"
            className="mt-1 w-full rounded-lg border p-2" value={title}
            onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label className="block text-sm">Describe the problem
          <textarea required minLength={10} maxLength={950} rows={5}
            aria-label="Maintenance problem description" value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="mt-1 w-full rounded-lg border p-2" />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm">Category
            <select aria-label="Maintenance category" value={category} className="mt-1 w-full rounded-lg border p-2"
              onChange={(event) => setCategory(event.target.value)}>
              {CATEGORIES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="text-sm">Urgency
            <select aria-label="Maintenance urgency" value={priority} className="mt-1 w-full rounded-lg border p-2"
              onChange={(event) => setPriority(event.target.value)}>
              {PRIORITIES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={permission} onChange={(event) => setPermission(event.target.checked)} />
          I authorize property staff to enter for this request, subject to applicable notice requirements.
        </label>
        <button disabled={saving || loading || !selectedId} type="submit"
          className="rounded-lg bg-slate-900 px-5 py-2 text-sm text-white disabled:opacity-50">
          {saving ? "Submitting…" : "Submit maintenance request"}
        </button>
      </form>
    </div>
  );
}
