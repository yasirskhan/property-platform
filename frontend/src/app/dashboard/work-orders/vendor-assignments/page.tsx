"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, apiPost } from "@/lib/api";

type Company = { id: number; company_name: string; is_active: boolean };
type Order = {
  id: number;
  property_id: number;
  title: string;
  status: string;
  assigned_to_id: number | null;
  vendor_id: number | null;
};
type Viewer = { role: string };

export default function WorkOrderVendorAssignmentPage() {
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [pending, setPending] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const who = await apiGet("/auth/me") as Viewer;
        if (!active) return;
        setViewer(who);
        if (who.role !== "ADMIN" && who.role !== "OWNER") {
          setError("Vendor-company assignments require an authorized administrator or owner.");
          return;
        }
        const [vendors, workOrders] = await Promise.all([
          apiGet("/api/vendors") as Promise<{ items: Company[] }>,
          apiGet("/work-orders/vendor-assignments") as Promise<Order[]>,
        ]);
        if (!active) return;
        setCompanies(vendors.items.filter((vendor) => vendor.is_active));
        setOrders(workOrders);
        setPending(Object.fromEntries(workOrders.map((order) => [
          order.id, order.vendor_id === null ? "" : String(order.vendor_id),
        ])));
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Vendor assignments unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, []);

  async function save(order: Order) {
    const selected = pending[order.id] ?? "";
    if (selected && !companies.some((company) => company.id === Number(selected))) {
      setError("Selected vendor is no longer available. Refresh the page.");
      return;
    }
    setBusy(order.id);
    setError(""); setMessage("");
    try {
      const updated = await apiPost(`/work-orders/${order.id}/vendor`, {
        vendor_id: selected ? Number(selected) : null,
      }) as Order;
      setOrders((old) => old.map((row) => row.id === updated.id ? updated : row));
      setMessage(`Work order #${order.id} vendor association saved. Crew assignment was unchanged.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Vendor assignment was not saved.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/vendors" className="text-sm text-slate-600 hover:underline">
        ← Vendor companies
      </Link>
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Work order vendor companies</h1>
        <p className="mt-1 text-sm text-slate-600">
          Link existing work orders to organization vendor companies. This is a recorded
          association, not a crew assignment, vendor dispatch, contract, or payment.
          Existing work-order statuses and assigned crew remain unchanged.
        </p>
      </header>
      {loading && <p className="text-sm text-slate-500">Loading authorized work orders…</p>}
      {error && <p role="alert" className="rounded border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded border border-green-200 p-3 text-sm text-green-800">{message}</p>}
      {!loading && viewer && (viewer.role === "ADMIN" || viewer.role === "OWNER") && (
        <div className="space-y-3">
          {orders.length === 0 && <p className="rounded border bg-white p-5 text-sm text-slate-600">
            There are no work orders available for vendor association.
          </p>}
          {orders.map((order) => {
            const selected = pending[order.id] ?? "";
            const isFinished = order.status === "closed" || order.status === "cancelled";
            const known = order.vendor_id !== null && !companies.some((vendor) => vendor.id === order.vendor_id);
            return (
              <section key={order.id} className="rounded-xl border bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="font-semibold">#{order.id} — {order.title}</h2>
                    <p className="text-xs text-slate-500">
                      Property #{order.property_id} · {order.status.replaceAll("_", " ")}
                      {" · "}Crew user #{order.assigned_to_id ?? "unassigned"}
                    </p>
                    {known && <p className="mt-1 text-xs text-amber-800">
                      A previous vendor association exists but the company is unavailable in the active directory.
                    </p>}
                  </div>
                  <div className="flex flex-wrap gap-2 items-center">
                    <label className="text-sm">
                      Vendor company
                      <select
                        aria-label={`Work order #${order.id} vendor company`}
                        disabled={isFinished || busy !== null}
                        value={selected}
                        onChange={(event) => setPending((old) => ({
                          ...old, [order.id]: event.target.value,
                        }))}
                        className="ml-2 rounded border px-3 py-2 text-sm"
                      >
                        <option value="">No company linked</option>
                        {known && <option value={order.vendor_id ?? ""}>
                          Unavailable company (current association)
                        </option>}
                        {companies.map((vendor) =>
                          <option value={vendor.id} key={vendor.id}>{vendor.company_name}</option>)}
                      </select>
                    </label>
                    <button type="button" disabled={isFinished || busy !== null ||
                      selected === (order.vendor_id === null ? "" : String(order.vendor_id))}
                      onClick={() => { void save(order); }}
                      className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
                    >
                      {busy === order.id ? "Saving…" : "Save link"}
                    </button>
                  </div>
                </div>
                {isFinished && <p className="mt-2 text-xs text-slate-500">
                  Finished work orders are read-only.
                </p>}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
