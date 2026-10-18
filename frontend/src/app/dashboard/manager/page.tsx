"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import Link from "next/link";

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
        workOrders: workOrders.filter((row: {status: string}) => row.status !== "closed" && row.status !== "cancelled").length,
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
      <Link href="/dashboard/maintenance/work-orders" className="mt-5 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">View work order queue</Link>
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