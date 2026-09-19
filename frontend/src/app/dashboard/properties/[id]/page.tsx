"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiDelete } from "@/lib/api";

type Property = {
  id: number;
  name: string;
  property_type: string;
  address_line1: string;
  address_line2: string | null;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  year_built: number | null;
  year_renovated: number | null;
  square_feet: number | null;
  stories: number | null;
  parking_spaces: number | null;
  parking_type: string | null;
  estimated_rent: string | null;
  security_deposit: string | null;
  ownership_status: string | null;
  description: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
};

type Unit = {
  id: number;
  unit_number: string;
  bedrooms: number;
  bathrooms: string;
  square_feet: number | null;
  monthly_rent: string;
  is_available: boolean;
};

type Me = { role: string };

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "units", label: "Units" },
  { id: "photos", label: "Photos" },
  { id: "utilities", label: "Utilities" },
  { id: "insurance", label: "Insurance" },
  { id: "financials", label: "Financials" },
  { id: "policies", label: "Policies" },
  { id: "amenities", label: "Amenities" },
  { id: "appliances", label: "Appliances" },
  { id: "improvements", label: "Improvements" },
  { id: "expenses", label: "Expenses" },
  { id: "history", label: "History" },
];

export default function PropertyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const propertyId = Number(params.id);

  const [me, setMe] = useState<Me | null>(null);
  const [property, setProperty] = useState<Property | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [meData, propData] = await Promise.all([
          apiGet("/auth/me"),
          apiGet(`/properties/${propertyId}`),
        ]);
        setMe(meData);
        setProperty(propData);
        setUnits(propData.units || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [propertyId]);

  async function handleDelete() {
    if (!confirm(`Delete "${property?.name}"? It will be hidden but not permanently removed.`)) return;
    setDeleting(true);
    try {
      const reason = prompt("Reason for deletion (optional):") || undefined;
      const query = reason ? `?reason=${encodeURIComponent(reason)}` : "";
      await apiDelete(`/properties/${propertyId}${query}`);
      router.push("/dashboard/properties");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      setDeleting(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;
  if (error || !property) return <div className="text-red-600">{error || "Not found"}</div>;

  const canEdit = me?.role === "admin" || me?.role === "owner" || me?.role === "manager";
  const canDelete = me?.role === "admin" || me?.role === "owner";

  return (
    <div>
      <Link href="/dashboard/properties" className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block">
        ← Back to properties
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{property.name}</h1>
          <p className="text-slate-500 mt-1">
            {property.address_line1}
            {property.address_line2 && `, ${property.address_line2}`}
            <br />
            {property.city}, {property.state} {property.zip_code}
          </p>
        </div>
        <div className="flex gap-3">
          {canEdit && (
            <Link
              href={`/dashboard/properties/${propertyId}/edit`}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              Edit
            </Link>
          )}
          {canDelete && property.is_active && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-sm px-4 py-2 border border-red-200 text-red-700 rounded-lg hover:bg-red-50 disabled:opacity-50"
            >
              {deleting ? "Deleting…" : "Delete"}
            </button>
          )}
        </div>
      </div>

      <div className="border-b border-slate-200 mb-6 overflow-x-auto">
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`whitespace-nowrap px-4 py-2 text-sm font-medium border-b-2 transition ${
                tab === t.id
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-900"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "overview" && <OverviewTab property={property} />}
      {tab === "units" && <UnitsTab units={units} propertyId={propertyId} canEdit={canEdit} />}
      {tab === "history" && <HistoryTab propertyId={propertyId} />}
      {tab !== "overview" && tab !== "units" && tab !== "history" && (
        <ComingSoonTab name={TABS.find((t) => t.id === tab)?.label || ""} />
      )}
    </div>
  );
}

function OverviewTab({ property }: { property: Property }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Section title="Basic Information">
        <Row label="Property Type" value={property.property_type?.replace("_", " ")} />
        <Row label="Year Built" value={property.year_built} />
        <Row label="Year Renovated" value={property.year_renovated} />
        <Row label="Square Feet" value={property.square_feet ? `${property.square_feet} sq ft` : null} />
        <Row label="Stories" value={property.stories} />
        <Row label="Parking Type" value={property.parking_type?.replace("_", " ")} />
        <Row label="Parking Spaces" value={property.parking_spaces} />
      </Section>

      <Section title="Financial">
        <Row label="Estimated Rent" value={property.estimated_rent ? `$${property.estimated_rent}/mo` : null} />
        <Row label="Security Deposit" value={property.security_deposit ? `$${property.security_deposit}` : null} />
        <Row label="Ownership" value={property.ownership_status?.replace("_", " ")} />
      </Section>

      <Section title="Description" full>
        <p className="text-slate-700 whitespace-pre-wrap">{property.description || "No description yet."}</p>
      </Section>

      {property.notes && (
        <Section title="Internal Notes" full>
          <p className="text-slate-700 whitespace-pre-wrap">{property.notes}</p>
        </Section>
      )}
    </div>
  );
}

function UnitsTab({
  units,
  propertyId,
  canEdit,
}: {
  units: Unit[];
  propertyId: number;
  canEdit: boolean;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-slate-600">
          {units.length} {units.length === 1 ? "unit" : "units"}
        </p>
        {canEdit && (
          <Link
            href={`/dashboard/properties/${propertyId}/units/new`}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Unit
          </Link>
        )}
      </div>
      {units.length === 0 ? (
        <p className="text-slate-500">No units yet.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">Unit</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">Beds/Baths</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">Sq Ft</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">Rent</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {units.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 font-medium">
                    <Link
                      href={`/dashboard/properties/${propertyId}/units/${u.id}/edit`}
                      className="text-slate-900 hover:text-slate-600 hover:underline"
                    >
                      {u.unit_number}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-slate-600">{u.bedrooms} bd / {u.bathrooms} ba</td>
                  <td className="px-6 py-4 text-slate-600">{u.square_feet || "—"}</td>
                  <td className="px-6 py-4 text-slate-600">${u.monthly_rent}</td>
                  <td className="px-6 py-4">
                    {u.is_available ? (
                      <span className="text-xs text-green-700 bg-green-50 px-2 py-1 rounded-full">Available</span>
                    ) : (
                      <span className="text-xs text-slate-700 bg-slate-100 px-2 py-1 rounded-full">Occupied</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function HistoryTab({ propertyId }: { propertyId: number }) {
  const [logs, setLogs] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet(`/properties/${propertyId}/history`)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, [propertyId]);

  if (loading) return <p className="text-slate-500">Loading history…</p>;
  if (logs.length === 0) return <p className="text-slate-500">No history yet.</p>;

  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
      {logs.map((log) => (
        <div key={log.id as number} className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs px-2 py-1 bg-slate-100 text-slate-700 rounded-full uppercase">
                {log.action as string}
              </span>
              <span className="text-sm text-slate-600">{log.user_name as string}</span>
            </div>
            <span className="text-xs text-slate-500">
              {new Date(log.created_at as string).toLocaleString()}
            </span>
          </div>
          {log.field_name && (
            <p className="text-sm text-slate-700 mt-2">
              <strong>{log.field_name as string}</strong>:{" "}
              <span className="text-slate-400">{(log.old_value as string) || "—"}</span>
              {" → "}
              <span className="text-slate-900">{(log.new_value as string) || "—"}</span>
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function ComingSoonTab({ name }: { name: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <p className="text-slate-400 text-sm">{name}</p>
      <p className="text-slate-500 mt-2">Coming in a future session.</p>
    </div>
  );
}

function Section({ title, children, full }: { title: string; children: React.ReactNode; full?: boolean }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 p-6 ${full ? "md:col-span-2" : ""}`}>
      <h2 className="font-semibold text-slate-900 mb-4">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-900 font-medium">{value || "—"}</span>
    </div>
  );
}