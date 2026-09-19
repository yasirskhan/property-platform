"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type Lease = { id: number; status: string; monthly_rent: string };
type WorkOrder = { id: number; title: string; status: string };

export default function TenantDashboard() {
  const [leases, setLeases] = useState<Lease[]>([]);
  const [orders, setOrders] = useState<WorkOrder[]>([]);

  useEffect(() => {
    apiGet("/leases").then(setLeases).catch(() => []);
    apiGet("/work-orders").then(setOrders).catch(() => []);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">My Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-3">My Lease</h2>
          {leases.length === 0 ? (
            <p className="text-slate-500 text-sm">No active lease.</p>
          ) : (
            <div>
              <p className="text-3xl font-bold text-slate-900">${leases[0].monthly_rent}</p>
              <p className="text-sm text-slate-500">per month · {leases[0].status}</p>
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-3">My Work Orders</h2>
          {orders.length === 0 ? (
            <p className="text-slate-500 text-sm">No work orders submitted.</p>
          ) : (
            <ul className="space-y-2">
              {orders.map((o) => (
                <li key={o.id} className="text-sm flex justify-between">
                  <span>{o.title}</span>
                  <span className="text-slate-500">{o.status}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}