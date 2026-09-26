"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Recipient = "PROPERTY" | "TENANT";
type LabelPreview = {
  title: string;
  headers: string[];
  rows: (string | number)[][];
  total: number;
};

export default function LabelsPage() {
  const [recipient, setRecipient] = useState<Recipient>("PROPERTY");
  const [propertyId, setPropertyId] = useState("");
  const [preview, setPreview] = useState<LabelPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState<{ recipient_type: Recipient; property_id?: string } | null>(null);

  async function load(nextRecipient: Recipient, nextPropertyId: string) {
    setLoading(true);
    setError("");
    setPreview(null);
    setApplied(null);
    const params = new URLSearchParams({ recipient_type: nextRecipient });
    if (nextPropertyId.trim()) params.set("property_id", nextPropertyId.trim());
    try {
      const data = await apiGet(`/api/reporting/labels/preview?${params.toString()}`) as LabelPreview;
      setPreview(data);
      setApplied({
        recipient_type: nextRecipient,
        ...(nextPropertyId.trim() ? { property_id: nextPropertyId.trim() } : {}),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load mailing labels.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load("PROPERTY", ""); }, []);

  return (
    <div>
      <div className="print:hidden mb-5">
        <Link href="/dashboard/reporting" className="text-sm text-slate-600 hover:text-slate-900">
          ← Reports
        </Link>
      </div>
      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-900">Create Labels Report</h1>
        <p className="mt-1 text-sm text-slate-500 print:hidden">
          Prepare a mail-merge CSV from recorded property addresses or current tenant leases.
          Tenant addresses use their property's recorded location, not an independent mailing address.
        </p>
      </header>
      <form
        onSubmit={(event) => { event.preventDefault(); void load(recipient, propertyId); }}
        className="print:hidden mb-5 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4"
      >
        <label className="block text-sm font-medium text-slate-700">
          Recipients
          <select value={recipient} onChange={(event) => setRecipient(event.target.value as Recipient)}
            className="mt-1 block rounded-lg border border-slate-300 px-3 py-2">
            <option value="PROPERTY">Properties</option>
            <option value="TENANT">Current tenants</option>
          </select>
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Property ID (optional)
          <input value={propertyId} min={1} type="number" step={1}
            onChange={(event) => setPropertyId(event.target.value)}
            placeholder="All accessible properties"
            className="mt-1 block w-56 rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        <button disabled={loading} type="submit"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {loading ? "Loading…" : "Generate labels"}
        </button>
      </form>
      {error && <p role="alert" className="mb-4 text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="print:hidden mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              {preview.total} label{preview.total === 1 ? "" : "s"}.
              CSV columns are ready for mail-merge mapping.
            </p>
            <ReportActions reportKey="mailing.labels" parameters={applied} />
          </div>
          {preview.rows.length === 0 ? (
            <p className="rounded-xl border bg-white p-8 text-sm text-slate-500">No matching mailing addresses.</p>
          ) : (
            <section aria-label="Mailing labels" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 print:grid-cols-3 print:gap-0">
              {preview.rows.map((row, index) => (
                <article key={index} className="break-inside-avoid rounded border border-slate-200 bg-white p-4 text-sm leading-5 print:rounded-none print:border-slate-300">
                  <div className="font-semibold">{String(row[0])}</div>
                  <div>{String(row[1])}</div>
                  {row[2] && <div>{String(row[2])}</div>}
                  <div>{String(row[3])}, {String(row[4])} {String(row[5])}</div>
                  {row[6] && <div>{String(row[6])}</div>}
                </article>
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}
