"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

export default function ManagerDashboard() {
  const [stats, setStats] = useState({ properties: 0, workOrders: 0, crew: 0 });

  useEffect(() => {
    Promise.all([
      apiGet("/properties").catch(() => []),
      apiGet("/work-orders").catch(() => []),
      apiGet("/users?role=crew").catch(() => []),
    ]).then(([properties, workOrders, crew]) => {
      setStats({
        properties: properties.length,
        workOrders: workOrders.length,
        crew: crew.length,
      });
    });
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Manager Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="My Properties" value={stats.properties} />
        <StatCard label="Open Work Orders" value={stats.workOrders} />
        <StatCard label="My Crew" value={stats.crew} />
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-3xl font-bold text-slate-900 mt-2">{value}</p>
    </div>
  );
}