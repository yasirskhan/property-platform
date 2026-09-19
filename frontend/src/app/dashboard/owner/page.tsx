"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

export default function OwnerDashboard() {
  const [stats, setStats] = useState({
    properties: 0,
    leases: 0,
    workOrders: 0,
    invoices: 0,
  });

  useEffect(() => {
    Promise.all([
      apiGet("/properties").catch(() => []),
      apiGet("/leases").catch(() => []),
      apiGet("/work-orders").catch(() => []),
    ]).then(async ([properties, leases, workOrders]) => {
      let invoiceCount = 0;
      for (const lease of leases) {
        try {
          const invoices = await apiGet(`/leases/${lease.id}/invoices`);
          invoiceCount += invoices.length;
        } catch {}
      }
      setStats({
        properties: properties.length,
        leases: leases.length,
        workOrders: workOrders.length,
        invoices: invoiceCount,
      });
    });
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Owner Dashboard</h1>
        <Link
          href="/dashboard/owner/settings/email"
          className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
        >
          Email Settings
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Properties" value={stats.properties} />
        <StatCard label="Active Leases" value={stats.leases} />
        <StatCard label="Work Orders" value={stats.workOrders} />
        <StatCard label="Rent Invoices" value={stats.invoices} />
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