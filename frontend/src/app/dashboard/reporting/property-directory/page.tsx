"use client";

import { useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = {
  title: string; headers: string[];
  rows: (string | number)[][]; total: number;
};

const PROPERTY_TYPES = [
  { value: "", label: "All property types" },
  { value: "single_family", label: "Single family" },
  { value: "multi_family", label: "Multi-family" },
  { value: "apartment", label: "Apartment" },
  { value: "condo", label: "Condo" },
  { value: "townhouse", label: "Townhouse" },
  { value: "commercial", label: "Commercial" },
  { value: "other", label: "Other" },
];

export default function PropertyDirectoryPage() {
  const [propertyId, setPropertyId] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const params = {
      ...(propertyId.trim() ? { property_id: propertyId.trim() } : {}),
      ...(propertyType ? { property_type: propertyType } : {}),
    };
    try {
      const query = new URLSearchParams(params).toString();
      const data = await apiGet(
        `/api/reporting/property-directory/preview${query ? "?" + query : ""}`
      ) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Property directory unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Property Directory</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorded active property addresses, types, and active unit records.
          Unit counts are configured inventory, not confirmed occupied units.
          No collected rent, inferred owners or financial postings are included.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm text-slate-700">Property ID (optional)
          <input min={1} type="number" step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-48 rounded-lg border border-slate-300 p-2" />
        </label>
        <label className="text-sm text-slate-700">Property type
          <select value={propertyType} onChange={(event) => setPropertyType(event.target.value)}
            className="mt-1 block rounded-lg border border-slate-300 p-2">
            {PROPERTY_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
          </select>
        </label>
        <button disabled={busy} type="submit"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load directory"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span><strong>{preview.total}</strong> active propert{preview.total === 1 ? "y" : "ies"}.</span>
            <ReportActions reportKey="property.directory" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-[1350px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                    {header}
                  </th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    {row.map((cell, j) => <td key={j} className="whitespace-nowrap px-3 py-2">{String(cell)}</td>)}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No matching active properties in your accessible scope.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
