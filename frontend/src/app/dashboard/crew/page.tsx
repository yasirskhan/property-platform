"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type WorkOrder = {
  id: number;
  title: string;
  status: string;
  priority: string;
};

export default function CrewDashboard() {
  const [orders, setOrders] = useState<WorkOrder[]>([]);

  useEffect(() => {
    apiGet("/work-orders").then(setOrders).catch(() => setOrders([]));
  }, []);

  const open = orders.filter((o) => o.status !== "closed" && o.status !== "cancelled");

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">My Work Orders</h1>
      {open.length === 0 ? (
        <p className="text-slate-500">No open work orders.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {open.map((o) => (
            <div key={o.id} className="p-4 flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">{o.title}</p>
                <p className="text-sm text-slate-500">Priority: {o.priority}</p>
              </div>
              <span className="text-xs px-3 py-1 bg-slate-100 text-slate-700 rounded-full">
                {o.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}