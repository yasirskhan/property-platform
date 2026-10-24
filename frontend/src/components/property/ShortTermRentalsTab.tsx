"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";

type Unit = { id: number; unit_number: string };
type PropertyPayload = { units?: Unit[] };
type Channel = {
  id: number;
  provider: "AIRBNB" | "VRBO";
  label: string;
  external_listing_id: string | null;
  public_listing_url: string | null;
  notes: string | null;
};
type NightlyPrice = {
  id: number;
  unit_id: number;
  night_date: string;
  nightly_rate: string;
  minimum_stay_nights: number;
  notes: string | null;
};
type Turnover = {
  id: number;
  unit_id: number;
  scheduled_start: string;
  scheduled_end: string;
  status: "SCHEDULED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
  cleaning_work_order_id: number | null;
  inspection_record_id: number | null;
  notes: string | null;
};

export default function ShortTermRentalsTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [units, setUnits] = useState<Unit[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [prices, setPrices] = useState<NightlyPrice[]>([]);
  const [turnovers, setTurnovers] = useState<Turnover[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const [provider, setProvider] = useState<"AIRBNB" | "VRBO">("AIRBNB");
  const [channelLabel, setChannelLabel] = useState("");
  const [externalListingId, setExternalListingId] = useState("");
  const [publicListingUrl, setPublicListingUrl] = useState("");

  const [priceUnitId, setPriceUnitId] = useState("");
  const [nightDate, setNightDate] = useState("");
  const [nightlyRate, setNightlyRate] = useState("");
  const [minimumStay, setMinimumStay] = useState("1");

  const [turnoverUnitId, setTurnoverUnitId] = useState("");
  const [turnoverStart, setTurnoverStart] = useState("");
  const [turnoverEnd, setTurnoverEnd] = useState("");
  const [turnoverStatus, setTurnoverStatus] = useState<Turnover["status"]>("SCHEDULED");
  const [workOrderId, setWorkOrderId] = useState("");
  const [inspectionId, setInspectionId] = useState("");

  const unitNames = useMemo(
    () => new Map(units.map((unit) => [unit.id, unit.unit_number])),
    [units]
  );

  async function load() {
    const [property, channelRows, priceRows, turnoverRows] = await Promise.all([
      apiGet(`/properties/${propertyId}`),
      apiGet(`/api/properties/${propertyId}/short-term-rentals/channels`),
      apiGet(`/api/properties/${propertyId}/short-term-rentals/nightly-prices`),
      apiGet(`/api/properties/${propertyId}/short-term-rentals/turnovers`),
    ]);
    setUnits(((property as PropertyPayload).units || []) as Unit[]);
    setChannels(channelRows as Channel[]);
    setPrices(priceRows as NightlyPrice[]);
    setTurnovers(turnoverRows as Turnover[]);
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await load();
        if (active) setError("");
      } catch (cause) {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Short-term rentals unavailable.");
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [propertyId]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Short-term rental action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createChannel(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/short-term-rentals/channels`, {
        provider,
        label: channelLabel,
        external_listing_id: externalListingId || undefined,
        public_listing_url: publicListingUrl || undefined,
      });
      setChannelLabel("");
      setExternalListingId("");
      setPublicListingUrl("");
      setMessage("Staff-recorded channel reference created. No provider connection was established.");
    });
  }

  async function createPrice(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/short-term-rentals/nightly-prices`, {
        unit_id: Number(priceUnitId),
        night_date: nightDate,
        nightly_rate: nightlyRate,
        minimum_stay_nights: Number(minimumStay),
      });
      setNightDate("");
      setNightlyRate("");
      setMinimumStay("1");
      setMessage("Nightly price recorded locally. No provider price was changed.");
    });
  }

  async function createTurnover(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/short-term-rentals/turnovers`, {
        unit_id: Number(turnoverUnitId),
        scheduled_start: turnoverStart,
        scheduled_end: turnoverEnd,
        status: turnoverStatus,
        cleaning_work_order_id: workOrderId ? Number(workOrderId) : undefined,
        inspection_record_id: inspectionId ? Number(inspectionId) : undefined,
      });
      setWorkOrderId("");
      setInspectionId("");
      setMessage("Turnover schedule recorded. Linked work orders or inspections were not modified.");
    });
  }

  async function archive(kind: "channels" | "nightly-prices" | "turnovers", id: number) {
    await run(async () => {
      await apiDelete(`/api/properties/${propertyId}/short-term-rentals/${kind}/${id}`);
      setMessage("Recorded short-term rental item archived.");
    });
  }

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Short-term Rentals</h2>
        <p className="mt-1 text-sm text-slate-600">
          Staff-entered Airbnb/Vrbo listing references, local nightly prices, and turnover schedules.
          This surface does not connect to provider APIs, synchronize reservations/calendars/pricing,
          or create bookings, payouts, charges, receipts, or accounting entries.
        </p>
      </div>

      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="space-y-3 rounded-xl border bg-white p-5">
          <h3 className="font-semibold">Airbnb / Vrbo references</h3>
          {canEdit && (
            <form className="grid gap-3" onSubmit={createChannel}>
              <label className="text-sm">Provider
                <select aria-label="Short-term rental provider" className="mt-1 w-full rounded border px-3 py-2" value={provider} onChange={(e) => setProvider(e.target.value as "AIRBNB" | "VRBO")}>
                  <option value="AIRBNB">Airbnb</option><option value="VRBO">Vrbo</option>
                </select>
              </label>
              <label className="text-sm">Staff label
                <input aria-label="Short-term rental channel label" required className="mt-1 w-full rounded border px-3 py-2" value={channelLabel} onChange={(e) => setChannelLabel(e.target.value)} />
              </label>
              <label className="text-sm">External listing ID
                <input aria-label="Short-term rental external listing ID" className="mt-1 w-full rounded border px-3 py-2" value={externalListingId} onChange={(e) => setExternalListingId(e.target.value)} />
              </label>
              <label className="text-sm">Public listing URL
                <input aria-label="Short-term rental public listing URL" type="url" className="mt-1 w-full rounded border px-3 py-2" value={publicListingUrl} onChange={(e) => setPublicListingUrl(e.target.value)} />
              </label>
              <button disabled={busy} className="rounded border px-4 py-2 text-sm font-medium">Add channel reference</button>
            </form>
          )}
          <div aria-label="Short-term rental channel list" className="space-y-2">
            {channels.length === 0 ? <p className="text-sm text-slate-500">No channel references.</p> : channels.map((row) => (
              <div key={row.id} className="flex items-center justify-between gap-3 rounded border p-3 text-sm">
                <div><strong>{row.provider}</strong> · {row.label}{row.external_listing_id ? ` · ${row.external_listing_id}` : ""}</div>
                {canEdit && <button type="button" disabled={busy} className="text-xs text-red-700" onClick={() => void archive("channels", row.id)}>Archive</button>}
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3 rounded-xl border bg-white p-5">
          <h3 className="font-semibold">Nightly pricing</h3>
          {canEdit && (
            <form className="grid gap-3 sm:grid-cols-2" onSubmit={createPrice}>
              <label className="text-sm">Unit
                <select aria-label="Nightly price unit" required className="mt-1 w-full rounded border px-3 py-2" value={priceUnitId} onChange={(e) => setPriceUnitId(e.target.value)}>
                  <option value="">Select unit</option>
                  {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.unit_number}</option>)}
                </select>
              </label>
              <label className="text-sm">Night
                <input aria-label="Nightly price date" required type="date" className="mt-1 w-full rounded border px-3 py-2" value={nightDate} onChange={(e) => setNightDate(e.target.value)} />
              </label>
              <label className="text-sm">Nightly rate
                <input aria-label="Nightly price rate" required type="number" min="0" step="0.01" className="mt-1 w-full rounded border px-3 py-2" value={nightlyRate} onChange={(e) => setNightlyRate(e.target.value)} />
              </label>
              <label className="text-sm">Minimum stay (nights)
                <input aria-label="Nightly price minimum stay" required type="number" min="1" max="365" className="mt-1 w-full rounded border px-3 py-2" value={minimumStay} onChange={(e) => setMinimumStay(e.target.value)} />
              </label>
              <button disabled={busy} className="rounded border px-4 py-2 text-sm font-medium sm:col-span-2">Record nightly price</button>
            </form>
          )}
          <div aria-label="Nightly price list" className="space-y-2">
            {prices.length === 0 ? <p className="text-sm text-slate-500">No nightly prices.</p> : prices.map((row) => (
              <div key={row.id} className="flex items-center justify-between gap-3 rounded border p-3 text-sm">
                <div><strong>{unitNames.get(row.unit_id) ?? row.unit_id}</strong> · {row.night_date} · USD {row.nightly_rate} · min {row.minimum_stay_nights}</div>
                {canEdit && <button type="button" disabled={busy} className="text-xs text-red-700" onClick={() => void archive("nightly-prices", row.id)}>Archive</button>}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="space-y-3 rounded-xl border bg-white p-5">
        <h3 className="font-semibold">Turnover scheduling</h3>
        <p className="text-xs text-slate-500">
          Optional work-order and inspection IDs must already exist for the same unit.
          Saving a turnover never changes those workflows.
        </p>
        {canEdit && (
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createTurnover}>
            <label className="text-sm">Unit
              <select aria-label="Turnover unit" required className="mt-1 w-full rounded border px-3 py-2" value={turnoverUnitId} onChange={(e) => setTurnoverUnitId(e.target.value)}>
                <option value="">Select unit</option>
                {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.unit_number}</option>)}
              </select>
            </label>
            <label className="text-sm">Start
              <input aria-label="Turnover start" required type="datetime-local" className="mt-1 w-full rounded border px-3 py-2" value={turnoverStart} onChange={(e) => setTurnoverStart(e.target.value)} />
            </label>
            <label className="text-sm">End
              <input aria-label="Turnover end" required type="datetime-local" className="mt-1 w-full rounded border px-3 py-2" value={turnoverEnd} onChange={(e) => setTurnoverEnd(e.target.value)} />
            </label>
            <label className="text-sm">Status
              <select aria-label="Turnover status" className="mt-1 w-full rounded border px-3 py-2" value={turnoverStatus} onChange={(e) => setTurnoverStatus(e.target.value as Turnover["status"])}>
                <option value="SCHEDULED">Scheduled</option>
                <option value="IN_PROGRESS">In progress</option>
                <option value="COMPLETED">Completed</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </label>
            <label className="text-sm">Existing cleaning work order ID
              <input aria-label="Turnover cleaning work order ID" type="number" min="1" className="mt-1 w-full rounded border px-3 py-2" value={workOrderId} onChange={(e) => setWorkOrderId(e.target.value)} />
            </label>
            <label className="text-sm">Existing inspection record ID
              <input aria-label="Turnover inspection record ID" type="number" min="1" className="mt-1 w-full rounded border px-3 py-2" value={inspectionId} onChange={(e) => setInspectionId(e.target.value)} />
            </label>
            <button disabled={busy} className="rounded border px-4 py-2 text-sm font-medium md:col-span-3">Record turnover schedule</button>
          </form>
        )}

        <div aria-label="Turnover schedule list" className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="border-b"><th className="p-2">Unit</th><th className="p-2">Start</th><th className="p-2">End</th><th className="p-2">Status</th><th className="p-2">References</th>{canEdit && <th className="p-2">Action</th>}</tr></thead>
            <tbody>{turnovers.map((row) => (
              <tr key={row.id} className="border-b">
                <td className="p-2">{unitNames.get(row.unit_id) ?? row.unit_id}</td>
                <td className="p-2">{row.scheduled_start}</td>
                <td className="p-2">{row.scheduled_end}</td>
                <td className="p-2">{row.status}</td>
                <td className="p-2">WO {row.cleaning_work_order_id ?? "—"} · Inspection {row.inspection_record_id ?? "—"}</td>
                {canEdit && <td className="p-2"><button type="button" disabled={busy} className="text-xs text-red-700" onClick={() => void archive("turnovers", row.id)}>Archive</button></td>}
              </tr>
            ))}</tbody>
          </table>
          {turnovers.length === 0 && <p className="p-2 text-sm text-slate-500">No turnover schedules.</p>}
        </div>
      </div>
    </section>
  );
}
