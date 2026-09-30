"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import RubsAllocationPanel from "@/components/property/RubsAllocationPanel";

type Utility = {
  utility_id: number;
  utility_type: string;
  bill_count: number;
  periods_complete: number;
  periods_missing_or_invalid: number;
  periods_overlapping: number;
  periods_duplicate: number;
};
type Readiness = {
  property_id: number;
  utility_count: number;
  items: Utility[];
  meter_readings_available: true;
  allocation_available: false;
  billing_available: false;
  meaning: string;
};
type MeterReading = {
  id: number;
  utility_id: number;
  unit_id: number | null;
  meter_identifier: string;
  reading_date: string;
  reading_value: string;
  unit_of_measure: string;
  source: "MANUAL" | "IMPORT";
  import_batch_key: string | null;
  notes: string | null;
  created_at: string;
};

function newRequestKey(prefix: string) {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

export default function RubsReadinessTab({ propertyId }: { propertyId: number }) {
  const [data, setData] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  const [selectedUtilityId, setSelectedUtilityId] = useState<number | null>(null);
  const [readings, setReadings] = useState<MeterReading[]>([]);
  const [readingError, setReadingError] = useState("");
  const [message, setMessage] = useState("");
  const [meterIdentifier, setMeterIdentifier] = useState("");
  const [readingDate, setReadingDate] = useState("");
  const [readingValue, setReadingValue] = useState("");
  const [unitOfMeasure, setUnitOfMeasure] = useState("");
  const [unitId, setUnitId] = useState("");
  const [notes, setNotes] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);

  async function loadReadings(utilityId: number) {
    try {
      const result = (await apiGet(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/meter-readings`
      )) as MeterReading[];
      setReadings(result);
      setReadingError("");
    } catch (cause) {
      setReadings([]);
      setReadingError(
        cause instanceof Error ? cause.message : "Meter readings unavailable."
      );
    }
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const result = (await apiGet(
          `/api/properties/${propertyId}/rubs-readiness`
        )) as Readiness;
        if (!active) return;
        setData(result);
        setError("");
        const firstUtility = result.items[0]?.utility_id ?? null;
        setSelectedUtilityId(firstUtility);
        if (firstUtility !== null) {
          await loadReadings(firstUtility);
        }
      } catch (cause) {
        if (active) {
          setError(
            cause instanceof Error ? cause.message : "RUBs readiness unavailable."
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [propertyId]);

  async function submitManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedUtilityId === null) return;
    setSaving(true);
    setMessage("");
    setReadingError("");
    try {
      await apiPost(
        `/api/properties/${propertyId}/rubs/utilities/${selectedUtilityId}/meter-readings`,
        {
          meter_identifier: meterIdentifier,
          reading_date: readingDate,
          reading_value: readingValue,
          unit_of_measure: unitOfMeasure,
          unit_id: unitId ? Number(unitId) : undefined,
          notes: notes || undefined,
          request_key: newRequestKey("manual-meter"),
        }
      );
      setReadingValue("");
      setNotes("");
      setMessage("Meter reading recorded as raw RUBs source data.");
      await loadReadings(selectedUtilityId);
    } catch (cause) {
      setReadingError(
        cause instanceof Error ? cause.message : "Unable to record meter reading."
      );
    } finally {
      setSaving(false);
    }
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedUtilityId === null || !csvFile) return;
    setSaving(true);
    setMessage("");
    setReadingError("");
    try {
      const result = (await apiPost(
        `/api/properties/${propertyId}/rubs/utilities/${selectedUtilityId}/meter-readings/import`,
        {
          request_key: newRequestKey("meter-import"),
          csv_text: await csvFile.text(),
        }
      )) as { created: number; replayed: number; total: number };
      setMessage(
        `Imported ${result.created} meter ${result.created === 1 ? "reading" : "readings"}.`
      );
      setCsvFile(null);
      const input = event.currentTarget.elements.namedItem("meterCsv");
      if (input instanceof HTMLInputElement) input.value = "";
      await loadReadings(selectedUtilityId);
    } catch (cause) {
      setReadingError(
        cause instanceof Error ? cause.message : "Unable to import meter readings."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-5 rounded-xl border bg-white p-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          RUBs — utility allocation readiness
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Shared-utility bill diagnostics plus raw meter-reading capture. Readings
          do not allocate a bill, create a tenant or owner charge, or post accounting.
        </p>
      </div>

      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {!data && !error && (
        <p className="text-sm text-slate-500">Loading readiness…</p>
      )}

      {data && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            {data.utility_count} shared{" "}
            {data.utility_count === 1 ? "utility" : "utilities"} recorded.
            Allocation and tenant/owner billing remain disabled.
          </p>

          {data.items.length === 0 ? (
            <p className="text-sm text-slate-500">
              No active shared utilities recorded. Review the Utilities tab before
              entering RUBs source readings.
            </p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="p-2">Utility</th>
                      <th className="p-2">Recorded bills</th>
                      <th className="p-2">Periods present</th>
                      <th className="p-2">Periods missing or invalid</th>
                      <th className="p-2">Duplicate periods</th>
                      <th className="p-2">Overlapping periods</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((row) => (
                      <tr key={row.utility_id} className="border-b">
                        <th scope="row" className="p-2 font-medium">
                          {row.utility_type} #{row.utility_id}
                        </th>
                        <td className="p-2">{row.bill_count}</td>
                        <td className="p-2">{row.periods_complete}</td>
                        <td className="p-2">
                          {row.periods_missing_or_invalid}
                        </td>
                        <td className="p-2">{row.periods_duplicate}</td>
                        <td className="p-2">{row.periods_overlapping}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="rounded-lg border p-4">
                <label className="block text-sm font-medium text-slate-800">
                  Shared utility for meter readings
                  <select
                    className="mt-1 w-full rounded border px-3 py-2"
                    value={selectedUtilityId ?? ""}
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      setSelectedUtilityId(value);
                      setMessage("");
                      void loadReadings(value);
                    }}
                  >
                    {data.items.map((row) => (
                      <option key={row.utility_id} value={row.utility_id}>
                        {row.utility_type} #{row.utility_id}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <form className="space-y-3 rounded-lg border p-4" onSubmit={submitManual}>
                  <h3 className="font-semibold text-slate-900">Manual meter reading</h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-sm">
                      Meter identifier
                      <input
                        required
                        maxLength={120}
                        className="mt-1 w-full rounded border px-3 py-2"
                        value={meterIdentifier}
                        onChange={(event) => setMeterIdentifier(event.target.value)}
                        placeholder="MASTER or SUB-101"
                      />
                    </label>
                    <label className="text-sm">
                      Reading date
                      <input
                        required
                        type="date"
                        className="mt-1 w-full rounded border px-3 py-2"
                        value={readingDate}
                        onChange={(event) => setReadingDate(event.target.value)}
                      />
                    </label>
                    <label className="text-sm">
                      Reading value
                      <input
                        required
                        type="number"
                        min="0"
                        step="any"
                        className="mt-1 w-full rounded border px-3 py-2"
                        value={readingValue}
                        onChange={(event) => setReadingValue(event.target.value)}
                      />
                    </label>
                    <label className="text-sm">
                      Unit of measure
                      <input
                        required
                        maxLength={32}
                        className="mt-1 w-full rounded border px-3 py-2"
                        value={unitOfMeasure}
                        onChange={(event) => setUnitOfMeasure(event.target.value)}
                        placeholder="gallons, kWh, therms"
                      />
                    </label>
                    <label className="text-sm">
                      Property unit ID (optional)
                      <input
                        type="number"
                        min="1"
                        className="mt-1 w-full rounded border px-3 py-2"
                        value={unitId}
                        onChange={(event) => setUnitId(event.target.value)}
                        placeholder="For a submeter"
                      />
                    </label>
                    <label className="text-sm sm:col-span-2">
                      Notes (optional)
                      <textarea
                        maxLength={1000}
                        className="mt-1 w-full rounded border px-3 py-2"
                        value={notes}
                        onChange={(event) => setNotes(event.target.value)}
                      />
                    </label>
                  </div>
                  <button
                    type="submit"
                    disabled={saving}
                    className="rounded border px-4 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    Record raw reading
                  </button>
                </form>

                <form className="space-y-3 rounded-lg border p-4" onSubmit={submitImport}>
                  <h3 className="font-semibold text-slate-900">Import meter readings</h3>
                  <p className="text-xs text-slate-600">
                    CSV columns: meter_identifier, reading_date, reading_value,
                    unit_of_measure, optional unit_id, optional notes. Dates use YYYY-MM-DD.
                    The batch is validated before any row is saved.
                  </p>
                  <input
                    name="meterCsv"
                    required
                    type="file"
                    accept=".csv,text/csv"
                    className="block w-full text-sm"
                    onChange={(event) => setCsvFile(event.target.files?.[0] ?? null)}
                  />
                  <button
                    type="submit"
                    disabled={saving || !csvFile}
                    className="rounded border px-4 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    Import CSV
                  </button>
                </form>
              </div>

              {message && (
                <p role="status" className="text-sm text-slate-700">
                  {message}
                </p>
              )}
              {readingError && (
                <p role="alert" className="text-sm text-red-700">
                  {readingError}
                </p>
              )}

              <RubsAllocationPanel
                propertyId={propertyId}
                utilityId={selectedUtilityId ?? data.items[0].utility_id}
              />

              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="p-2">Date</th>
                      <th className="p-2">Meter</th>
                      <th className="p-2">Property unit</th>
                      <th className="p-2">Reading</th>
                      <th className="p-2">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {readings.length === 0 ? (
                      <tr>
                        <td className="p-3 text-slate-500" colSpan={5}>
                          No raw meter readings recorded for this shared utility.
                        </td>
                      </tr>
                    ) : (
                      readings.map((row) => (
                        <tr key={row.id} className="border-b">
                          <td className="p-2">{row.reading_date}</td>
                          <td className="p-2">{row.meter_identifier}</td>
                          <td className="p-2">
                            {row.unit_id === null ? "Property meter" : `Unit #${row.unit_id}`}
                          </td>
                          <td className="p-2">
                            {row.reading_value} {row.unit_of_measure}
                          </td>
                          <td className="p-2">{row.source}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <p className="text-xs text-slate-500">
            Future allocation requires reviewed eligibility and calculation rules,
            supported bill periods, and approved tenant/owner charge logic. Raw readings
            are not themselves billable amounts. Duplicate/overlapping utility-bill
            periods still require manual source review.
          </p>
        </div>
      )}
    </section>
  );
}
