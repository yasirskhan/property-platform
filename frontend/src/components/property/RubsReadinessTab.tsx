"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type Utility = {
  utility_id: number;
  utility_type: string;
  bill_count: number;
  periods_complete: number;
  periods_missing_or_invalid: number;
};
type Readiness = {
  property_id: number;
  utility_count: number;
  items: Utility[];
  allocation_available: false;
  billing_available: false;
  meaning: string;
};

export default function RubsReadinessTab({ propertyId }: { propertyId: number }) {
  const [data, setData] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const result=await apiGet(`/api/properties/${propertyId}/rubs-readiness`) as Readiness;
        if (active) {setData(result);setError("");}
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "RUBs readiness unavailable.");
      }
    })();
    return () => {active=false;};
  }, [propertyId]);
  return <section className="space-y-4 rounded-xl border bg-white p-5">
    <h2 className="text-lg font-semibold text-slate-900">RUBs — utility allocation readiness</h2>
    <p className="text-sm text-slate-600">
      Read-only inventory of recorded shared utilities and bill-period completeness.
      This is not a billing, allocation or compliance calculation. No tenant charges
      or accounting entries can be created from this tab.
    </p>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {!data && !error && <p className="text-sm text-slate-500">Loading readiness…</p>}
    {data && <div className="space-y-3">
      <p className="text-sm text-slate-600">
        {data.utility_count} shared {data.utility_count === 1 ? "utility" : "utilities"} recorded.
        Allocation and tenant billing are not enabled.
      </p>
      {data.items.length===0
        ? <p className="text-sm text-slate-500">No active shared utilities recorded.
          Review the Utilities tab before planning a ratio-billing method.</p>
        : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <thead><tr className="border-b">
            <th className="p-2">Utility</th><th className="p-2">Recorded bills</th>
            <th className="p-2">Periods present</th><th className="p-2">Periods missing or invalid</th>
          </tr></thead>
          <tbody>{data.items.map(row=><tr key={row.utility_id} className="border-b">
            <th scope="row" className="p-2 font-medium">{row.utility_type} #{row.utility_id}</th>
            <td className="p-2">{row.bill_count}</td>
            <td className="p-2">{row.periods_complete}</td>
            <td className="p-2">{row.periods_missing_or_invalid}</td>
          </tr>)}</tbody>
        </table></div>}
      <p className="text-xs text-slate-500">
        Future allocation requires verified legal eligibility, supported calculation rules,
        meter or occupancy inputs, approved periods and reviewed tenant charges.
        Current utility bills do not establish billable amounts.
      </p>
    </div>}
  </section>;
}
