"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";

type Interest = {
  id: number;
  program_id: number;
  prospect_id: number;
  contact_name: string;
  recorded_at: string;
};
type Prospect = { id: number; property_id: number; contact_name: string };
type ProspectList = { items: Prospect[] };

export default function AffordableInterestLog({
  propertyId, programId, canEdit, onClose,
}: { propertyId: number; programId: number; canEdit: boolean; onClose: () => void }) {
  const [rows, setRows] = useState<Interest[]>([]);
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [prospectId, setProspectId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const path = `/api/properties/${propertyId}/affordable-programs/${programId}/interest`;

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const result = await apiGet(path) as Interest[];
        if (!active) return;
        setRows(result);
        if (canEdit) {
          const data = await apiGet(`/api/leasing/prospects?property_id=${propertyId}`) as ProspectList;
          if (active) setProspects(data.items.filter((p) => p.property_id === propertyId));
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Program interest is unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [path, propertyId, canEdit]);

  async function record(event: React.FormEvent) {
    event.preventDefault();
    if (!prospectId || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const row = await apiPost(path, { prospect_id: Number(prospectId) }) as Interest;
      setRows((prior) => [...prior, row]);
      setProspectId("");
      setMessage("Interest recorded. No application, eligibility decision or waiting-list priority was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not record program interest.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(row: Interest) {
    if (busy || !window.confirm("Archive this staff-recorded interest? This does not change assistance.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(`${path}/${row.id}`);
      setRows((prior) => prior.filter((item) => item.id !== row.id));
      setMessage("Staff-recorded interest archived. No assistance was changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not archive interest.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-blue-200 bg-blue-50 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold text-slate-900">Staff-recorded program interest</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700 underline">Close</button>
      </div>
      <p className="text-sm text-slate-700">
        This is an informal CRM interest register, not an official ranked waiting list,
        approved admission, verified voucher, income certification or eligibility decision.
        No automatic priority, offers, messages or payments are created.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading interest…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && rows.length === 0 && <p className="text-sm text-slate-600">No interest recorded.</p>}
      {!loading && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="border-b">
              <th className="p-2">CRM contact</th>
              <th className="p-2">Staff recorded on</th>
              {canEdit && <th className="p-2">Action</th>}
            </tr></thead>
            <tbody>{rows.map((row) => (
              <tr key={row.id} className="border-b">
                <td className="p-2">{row.contact_name}</td>
                <td className="p-2">{row.recorded_at.slice(0, 10)}</td>
                {canEdit && <td className="p-2">
                  <button type="button" disabled={busy} onClick={() => { void archive(row); }}
                    className="text-red-700 underline disabled:opacity-50">Archive</button>
                </td>}
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void record(event); }}
          className="flex flex-wrap items-end gap-3 border-t pt-3">
          <label className="text-sm text-slate-700">Existing authorized CRM prospect
            <select required value={prospectId} onChange={(event) => setProspectId(event.target.value)}
              className="mt-1 block min-w-52 rounded border border-slate-300 p-2">
              <option value="">Select existing prospect</option>
              {prospects.filter((p) => !rows.some((row) => row.prospect_id === p.id)).map((p) => (
                <option key={p.id} value={p.id}>{p.contact_name}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={busy || !prospectId}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            {busy ? "Recording…" : "Record interest"}
          </button>
        </form>
      )}
    </section>
  );
}
