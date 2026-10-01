"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Context = {
  units: { id: number; unit_number: string }[];
  tenants: { id: number; name: string; email: string }[];
};
type Cycle = {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
};
type Bed = {
  id: number;
  unit_id: number;
  bed_label: string;
};
type BedLease = {
  id: number;
  unit_id: number;
  bed_id: number;
  bed_label: string;
  tenant_id: number;
  tenant_name: string;
  tenant_email: string;
  academic_cycle_id: number;
  academic_cycle_name: string;
  start_date: string;
  end_date: string;
  monthly_rent: string;
  security_deposit: string;
  due_day: number;
  status: string;
};
type Guarantor = {
  id: number;
  property_id: number;
  lease_id: number;
  full_name: string;
  email: string;
  phone: string | null;
  relationship_to_tenant: string | null;
  status: string;
};

export default function StudentHousingTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [context, setContext] = useState<Context>({ units: [], tenants: [] });
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [beds, setBeds] = useState<Bed[]>([]);
  const [leases, setLeases] = useState<BedLease[]>([]);
  const [guarantors, setGuarantors] = useState<Guarantor[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const [cycleName, setCycleName] = useState("");
  const [cycleStart, setCycleStart] = useState("");
  const [cycleEnd, setCycleEnd] = useState("");

  const [bedUnitId, setBedUnitId] = useState("");
  const [bedLabel, setBedLabel] = useState("");

  const [leaseBedId, setLeaseBedId] = useState("");
  const [leaseTenantId, setLeaseTenantId] = useState("");
  const [leaseCycleId, setLeaseCycleId] = useState("");
  const [leaseStart, setLeaseStart] = useState("");
  const [leaseEnd, setLeaseEnd] = useState("");
  const [monthlyRent, setMonthlyRent] = useState("");
  const [securityDeposit, setSecurityDeposit] = useState("0");
  const [dueDay, setDueDay] = useState("1");

  const [guarantorLeaseId, setGuarantorLeaseId] = useState("");
  const [guarantorName, setGuarantorName] = useState("");
  const [guarantorEmail, setGuarantorEmail] = useState("");
  const [guarantorPhone, setGuarantorPhone] = useState("");
  const [guarantorRelationship, setGuarantorRelationship] = useState("");

  const unitName = useMemo(
    () => new Map(context.units.map((unit) => [unit.id, unit.unit_number])),
    [context.units]
  );

  async function load() {
    const [ctx, cycleRows, bedRows, leaseRows, guarantorRows] = await Promise.all([
      apiGet(`/api/properties/${propertyId}/student-housing/context`),
      apiGet(`/api/properties/${propertyId}/student-housing/academic-cycles`),
      apiGet(`/api/properties/${propertyId}/student-housing/beds`),
      apiGet(`/api/properties/${propertyId}/student-housing/bed-leases`),
      apiGet(`/api/properties/${propertyId}/student-housing/guarantors`),
    ]);
    setContext(ctx as Context);
    setCycles(cycleRows as Cycle[]);
    setBeds(bedRows as Bed[]);
    setLeases(leaseRows as BedLease[]);
    setGuarantors(guarantorRows as Guarantor[]);
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await load();
        if (active) setError("");
      } catch (cause) {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Student Housing unavailable.");
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [propertyId]);

  async function run(action: () => Promise<void>) {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await action();
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Student Housing action failed.");
    } finally {
      setSaving(false);
    }
  }

  async function createCycle(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/student-housing/academic-cycles`, {
        name: cycleName,
        start_date: cycleStart,
        end_date: cycleEnd,
      });
      setCycleName("");
      setMessage("Academic cycle created.");
    });
  }

  async function createBed(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/student-housing/beds`, {
        unit_id: Number(bedUnitId),
        bed_label: bedLabel,
      });
      setBedLabel("");
      setMessage("Bed inventory created.");
    });
  }

  async function createBedLease(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/student-housing/bed-leases`, {
        bed_id: Number(leaseBedId),
        tenant_id: Number(leaseTenantId),
        academic_cycle_id: Number(leaseCycleId),
        start_date: leaseStart,
        end_date: leaseEnd,
        monthly_rent: monthlyRent,
        security_deposit: securityDeposit || "0",
        due_day: Number(dueDay),
      });
      setMessage("Draft by-the-bed lease created in the standard lease lifecycle.");
    });
  }

  async function createGuarantor(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(
        `/api/properties/${propertyId}/student-housing/bed-leases/${guarantorLeaseId}/guarantors`,
        {
          full_name: guarantorName,
          email: guarantorEmail,
          phone: guarantorPhone || undefined,
          relationship_to_tenant: guarantorRelationship || undefined,
        }
      );
      setGuarantorName("");
      setGuarantorEmail("");
      setGuarantorPhone("");
      setGuarantorRelationship("");
      setMessage("Guarantor workflow record created.");
    });
  }

  async function transitionGuarantor(id: number, action: "mark-requested" | "record-received" | "cancel") {
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/student-housing/guarantors/${id}/${action}`);
      setMessage(
        action === "mark-requested"
          ? "Guarantor request marked as externally requested."
          : action === "record-received"
            ? "Guarantor document receipt recorded."
            : "Guarantor workflow cancelled."
      );
    });
  }

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Student Housing</h2>
        <p className="mt-1 text-sm text-slate-600">
          Academic cycles, bed inventory, by-the-bed leases, and staff-tracked guarantor workflow.
          Bed leases use the standard lease signature, activation, invoice, and payment lifecycle.
          Guarantor status does not itself establish legal guaranty validity or financial liability.
        </p>
      </div>

      {message && <p role="status" className="text-sm text-slate-700">{message}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="space-y-3 rounded-xl border bg-white p-5">
          <h3 className="font-semibold">Academic cycles</h3>
          {canEdit && (
            <form className="grid gap-2 sm:grid-cols-2" onSubmit={createCycle}>
              <label className="text-sm sm:col-span-2">Cycle name
                <input aria-label="Academic cycle name" required className="mt-1 w-full rounded border px-3 py-2" value={cycleName} onChange={(e) => setCycleName(e.target.value)} />
              </label>
              <label className="text-sm">Start date
                <input aria-label="Academic cycle start date" required type="date" className="mt-1 w-full rounded border px-3 py-2" value={cycleStart} onChange={(e) => setCycleStart(e.target.value)} />
              </label>
              <label className="text-sm">End date
                <input aria-label="Academic cycle end date" required type="date" className="mt-1 w-full rounded border px-3 py-2" value={cycleEnd} onChange={(e) => setCycleEnd(e.target.value)} />
              </label>
              <button disabled={saving} className="rounded border px-4 py-2 text-sm font-medium sm:col-span-2">Create academic cycle</button>
            </form>
          )}
          <div aria-label="Academic cycle list" className="space-y-2">
            {cycles.length === 0 ? <p className="text-sm text-slate-500">No academic cycles.</p> : cycles.map((cycle) => (
              <div key={cycle.id} className="rounded border p-3 text-sm">
                <strong>{cycle.name}</strong><div>{cycle.start_date} to {cycle.end_date}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3 rounded-xl border bg-white p-5">
          <h3 className="font-semibold">Bed inventory</h3>
          {canEdit && (
            <form className="grid gap-2 sm:grid-cols-2" onSubmit={createBed}>
              <label className="text-sm">Unit
                <select aria-label="Student bed unit" required className="mt-1 w-full rounded border px-3 py-2" value={bedUnitId} onChange={(e) => setBedUnitId(e.target.value)}>
                  <option value="">Select unit</option>
                  {context.units.map((unit) => <option key={unit.id} value={unit.id}>{unit.unit_number}</option>)}
                </select>
              </label>
              <label className="text-sm">Bed label
                <input aria-label="Student bed label" required className="mt-1 w-full rounded border px-3 py-2" value={bedLabel} onChange={(e) => setBedLabel(e.target.value)} />
              </label>
              <button disabled={saving} className="rounded border px-4 py-2 text-sm font-medium sm:col-span-2">Create bed</button>
            </form>
          )}
          <div aria-label="Student bed list" className="space-y-2">
            {beds.length === 0 ? <p className="text-sm text-slate-500">No bed inventory.</p> : beds.map((bed) => (
              <div key={bed.id} className="rounded border p-3 text-sm"><strong>{bed.bed_label}</strong> · Unit {unitName.get(bed.unit_id) ?? bed.unit_id}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="space-y-3 rounded-xl border bg-white p-5">
        <h3 className="font-semibold">By-the-bed leases</h3>
        {canEdit && (
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createBedLease}>
            <label className="text-sm">Bed
              <select aria-label="Bed lease bed" required className="mt-1 w-full rounded border px-3 py-2" value={leaseBedId} onChange={(e) => setLeaseBedId(e.target.value)}>
                <option value="">Select bed</option>
                {beds.map((bed) => <option key={bed.id} value={bed.id}>{unitName.get(bed.unit_id) ?? bed.unit_id} · {bed.bed_label}</option>)}
              </select>
            </label>
            <label className="text-sm">Tenant
              <select aria-label="Bed lease tenant" required className="mt-1 w-full rounded border px-3 py-2" value={leaseTenantId} onChange={(e) => setLeaseTenantId(e.target.value)}>
                <option value="">Select tenant</option>
                {context.tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name} · {tenant.email}</option>)}
              </select>
            </label>
            <label className="text-sm">Academic cycle
              <select aria-label="Bed lease academic cycle" required className="mt-1 w-full rounded border px-3 py-2" value={leaseCycleId} onChange={(e) => setLeaseCycleId(e.target.value)}>
                <option value="">Select cycle</option>
                {cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
              </select>
            </label>
            <label className="text-sm">Lease start
              <input aria-label="Bed lease start date" required type="date" className="mt-1 w-full rounded border px-3 py-2" value={leaseStart} onChange={(e) => setLeaseStart(e.target.value)} />
            </label>
            <label className="text-sm">Lease end
              <input aria-label="Bed lease end date" required type="date" className="mt-1 w-full rounded border px-3 py-2" value={leaseEnd} onChange={(e) => setLeaseEnd(e.target.value)} />
            </label>
            <label className="text-sm">Monthly rent
              <input aria-label="Bed lease monthly rent" required type="number" min="0" step="0.01" className="mt-1 w-full rounded border px-3 py-2" value={monthlyRent} onChange={(e) => setMonthlyRent(e.target.value)} />
            </label>
            <label className="text-sm">Security deposit
              <input aria-label="Bed lease security deposit" type="number" min="0" step="0.01" className="mt-1 w-full rounded border px-3 py-2" value={securityDeposit} onChange={(e) => setSecurityDeposit(e.target.value)} />
            </label>
            <label className="text-sm">Due day
              <input aria-label="Bed lease due day" required type="number" min="1" max="28" className="mt-1 w-full rounded border px-3 py-2" value={dueDay} onChange={(e) => setDueDay(e.target.value)} />
            </label>
            <div className="flex items-end"><button disabled={saving} className="w-full rounded border px-4 py-2 text-sm font-medium">Create draft bed lease</button></div>
          </form>
        )}
        <div aria-label="Student bed lease list" className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="border-b"><th className="p-2">Bed</th><th className="p-2">Tenant</th><th className="p-2">Cycle</th><th className="p-2">Dates</th><th className="p-2">Rent</th><th className="p-2">Status</th></tr></thead>
            <tbody>{leases.map((lease) => (
              <tr key={lease.id} className="border-b">
                <td className="p-2">{unitName.get(lease.unit_id) ?? lease.unit_id} · {lease.bed_label}</td>
                <td className="p-2">{lease.tenant_name}</td>
                <td className="p-2">{lease.academic_cycle_name}</td>
                <td className="p-2">{lease.start_date} to {lease.end_date}</td>
                <td className="p-2">USD {lease.monthly_rent}</td>
                <td className="p-2">{lease.status}</td>
              </tr>
            ))}</tbody>
          </table>
          {leases.length === 0 && <p className="p-2 text-sm text-slate-500">No by-the-bed leases.</p>}
        </div>
      </div>

      <div className="space-y-3 rounded-xl border bg-white p-5">
        <h3 className="font-semibold">Guarantor workflow</h3>
        <p className="text-xs text-slate-500">Operational status only. Document receipt is not a legal-validity determination.</p>
        {canEdit && (
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createGuarantor}>
            <label className="text-sm">Bed lease
              <select aria-label="Guarantor bed lease" required className="mt-1 w-full rounded border px-3 py-2" value={guarantorLeaseId} onChange={(e) => setGuarantorLeaseId(e.target.value)}>
                <option value="">Select lease</option>
                {leases.map((lease) => <option key={lease.id} value={lease.id}>#{lease.id} · {lease.tenant_name} · {lease.bed_label}</option>)}
              </select>
            </label>
            <label className="text-sm">Full name
              <input aria-label="Guarantor full name" required className="mt-1 w-full rounded border px-3 py-2" value={guarantorName} onChange={(e) => setGuarantorName(e.target.value)} />
            </label>
            <label className="text-sm">Email
              <input aria-label="Guarantor email" required type="email" className="mt-1 w-full rounded border px-3 py-2" value={guarantorEmail} onChange={(e) => setGuarantorEmail(e.target.value)} />
            </label>
            <label className="text-sm">Phone
              <input aria-label="Guarantor phone" className="mt-1 w-full rounded border px-3 py-2" value={guarantorPhone} onChange={(e) => setGuarantorPhone(e.target.value)} />
            </label>
            <label className="text-sm">Relationship
              <input aria-label="Guarantor relationship" className="mt-1 w-full rounded border px-3 py-2" value={guarantorRelationship} onChange={(e) => setGuarantorRelationship(e.target.value)} />
            </label>
            <div className="flex items-end"><button disabled={saving} className="w-full rounded border px-4 py-2 text-sm font-medium">Create guarantor workflow</button></div>
          </form>
        )}

        <div aria-label="Guarantor workflow list" className="space-y-2">
          {guarantors.length === 0 ? <p className="text-sm text-slate-500">No guarantor workflow records.</p> : guarantors.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3 text-sm">
              <div><strong>{row.full_name}</strong> · {row.email} · Lease #{row.lease_id} · <span>{row.status}</span></div>
              {canEdit && <div className="flex flex-wrap gap-2">
                {row.status === "DRAFT" && <button type="button" disabled={saving} className="rounded border px-3 py-1 text-xs" onClick={() => void transitionGuarantor(row.id, "mark-requested")}>Mark requested</button>}
                {row.status === "REQUESTED" && <button type="button" disabled={saving} className="rounded border px-3 py-1 text-xs" onClick={() => void transitionGuarantor(row.id, "record-received")}>Record document received</button>}
                {(row.status === "DRAFT" || row.status === "REQUESTED") && <button type="button" disabled={saving} className="rounded border px-3 py-1 text-xs" onClick={() => void transitionGuarantor(row.id, "cancel")}>Cancel workflow</button>}
              </div>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
