"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  GPRCandidateList,
  listGPRCandidates,
  postGPR,
} from "@/lib/journalEntries";
import { formatMoney } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function PostGPRPage() {
  const { prefs } = useDisplay();
  const [month, setMonth] = useState(currentMonth);
  const [data, setData] = useState<GPRCandidateList | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await listGPRCandidates(`${month}-01`);
      setData(result);
      setSelected(
        new Set(
          result.items
            .filter((row) => !row.already_posted)
            .map((row) => row.unit_id)
        )
      );
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "GPR candidates failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  const unposted = data?.items.filter((row) => !row.already_posted) ?? [];
  const selectedRows = unposted.filter((row) => selected.has(row.unit_id));
  const totals = useMemo(
    () =>
      selectedRows.reduce(
        (acc, row) => ({
          market: acc.market + Number(row.market_rent),
          scheduled: acc.scheduled + Number(row.scheduled_rent),
          lossGain: acc.lossGain + Number(row.loss_gain),
        }),
        { market: 0, scheduled: 0, lossGain: 0 }
      ),
    [selectedRows]
  );

  function toggle(unitId: number) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(unitId)) next.delete(unitId);
      else next.add(unitId);
      return next;
    });
  }

  async function submit() {
    if (!selected.size) return;
    setPosting(true);
    setError("");
    setMessage("");
    try {
      const result = await postGPR(`${month}-01`, Array.from(selected));
      setMessage(`Posted ${result.posted} GPR journal ${result.posted === 1 ? "entry" : "entries"}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "GPR posting failed");
    } finally {
      setPosting(false);
    }
  }

  return (
    <div
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
      className="max-w-6xl"
    >
      <Link
        href="/dashboard/accounting/journal-entries"
        className="text-sm text-slate-500 hover:text-slate-800"
      >
        ← Back to Journal Entries
      </Link>

      <div className="mt-4 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Post Gross Potential Rent
        </h1>
        <p className="text-slate-500 mt-1">
          Reclassify scheduled rent into Gross Potential Rent and Loss/Gain for the selected month.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-4 mb-5 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Month</label>
          <input
            type="month"
            value={month}
            onChange={(event) => setMonth(event.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div className="text-sm text-slate-600">
          {data ? `${data.unposted} of ${data.total} units available to post` : "Loading…"}
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-5">
          {error}
        </div>
      )}
      {message && (
        <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3 mb-5">
          {message}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left">
                <input
                  type="checkbox"
                  aria-label="Select all unposted GPR rows"
                  checked={unposted.length > 0 && selected.size === unposted.length}
                  onChange={(event) =>
                    setSelected(
                      event.target.checked
                        ? new Set(unposted.map((row) => row.unit_id))
                        : new Set()
                    )
                  }
                />
              </th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Property</th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Unit</th>
              <th className="px-4 py-3 text-right font-medium text-slate-700">Market Rent</th>
              <th className="px-4 py-3 text-right font-medium text-slate-700">Scheduled Rent</th>
              <th className="px-4 py-3 text-right font-medium text-slate-700">Loss / Gain</th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  Loading GPR rows…
                </td>
              </tr>
            )}
            {!loading && (data?.items.length ?? 0) === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No active units with market rent were found.
                </td>
              </tr>
            )}
            {!loading &&
              data?.items.map((row) => (
                <tr key={row.unit_id} className="border-t border-slate-100">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label={`Select ${row.property_name} unit ${row.unit_number}`}
                      disabled={row.already_posted}
                      checked={!row.already_posted && selected.has(row.unit_id)}
                      onChange={() => toggle(row.unit_id)}
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-800">{row.property_name}</td>
                  <td className="px-4 py-3 text-slate-700">{row.unit_number}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatMoney(row.market_rent)}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatMoney(row.scheduled_rent)}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatMoney(row.loss_gain)}</td>
                  <td className="px-4 py-3">
                    {row.already_posted ? (
                      <span className="text-xs text-green-700 bg-green-50 px-2 py-1 rounded-full">
                        Posted
                      </span>
                    ) : row.lease_id ? (
                      <span className="text-xs text-slate-700">Occupied</span>
                    ) : (
                      <span className="text-xs text-amber-700">Vacant</span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
          {selectedRows.length > 0 && (
            <tfoot className="bg-slate-50 border-t border-slate-200 font-medium">
              <tr>
                <td colSpan={3} className="px-4 py-3 text-right">
                  Selected totals
                </td>
                <td className="px-4 py-3 text-right font-mono">{formatMoney(totals.market)}</td>
                <td className="px-4 py-3 text-right font-mono">{formatMoney(totals.scheduled)}</td>
                <td className="px-4 py-3 text-right font-mono">{formatMoney(totals.lossGain)}</td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          disabled={posting || selected.size === 0}
          onClick={() => void submit()}
          className="px-5 py-2.5 rounded-lg bg-slate-900 text-white font-medium disabled:opacity-50"
        >
          {posting ? "Posting…" : `Post ${selected.size} Selected`}
        </button>
      </div>
    </div>
  );
}
