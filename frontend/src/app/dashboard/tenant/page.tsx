"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import Link from "next/link";
import { formatMoney } from "@/lib/money";

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
              <p className="text-3xl font-bold text-slate-900 font-mono">
                {formatMoney(leases[0].monthly_rent)}
              </p>
              <p className="text-sm text-slate-500">
                per month · {leases[0].status}
              </p>
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-3">My Work Orders</h2>
          <Link href="/dashboard/maintenance/work-orders/new" className="mb-3 inline-block rounded-lg border px-3 py-2 text-sm">Request maintenance</Link>
          {orders.length === 0 ? (
            <p className="text-slate-500 text-sm">No work orders submitted.</p>
          ) : (
            <ul className="space-y-2">
              {[...orders].sort((a, b) =>
                Number(["closed", "cancelled"].includes(a.status)) -
                Number(["closed", "cancelled"].includes(b.status))
              ).map((order) => (
                <li key={order.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                  <Link className="font-medium text-blue-800 hover:underline"
                    href={`/dashboard/maintenance/work-orders/${order.id}`}>
                    #{order.id} · {order.title}
                  </Link>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                    {order.status.replaceAll("_", " ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}