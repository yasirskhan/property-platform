"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

export default function AdminDashboard() {
  const [stats, setStats] = useState({ users: 0, properties: 0, leases: 0, workOrders: 0 });

  useEffect(() => {
    Promise.all([
      apiGet("/users").catch(() => []),
      apiGet("/properties").catch(() => []),
      apiGet("/leases").catch(() => []),
      apiGet("/work-orders").catch(() => []),
    ]).then(([users, properties, leases, workOrders]) => {
      setStats({
        users: users.length,
        properties: properties.length,
        leases: leases.length,
        workOrders: workOrders.length,
      });
    });
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Admin Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Users" value={stats.users} />
        <StatCard label="Properties" value={stats.properties} />
        <StatCard label="Leases" value={stats.leases} />
        <StatCard label="Work Orders" value={stats.workOrders} />
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