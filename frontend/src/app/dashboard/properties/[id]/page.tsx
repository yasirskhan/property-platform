"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiDelete } from "@/lib/api";
import UtilitiesTab from "@/components/property/UtilitiesTab";
import InsuranceTab from "@/components/property/InsuranceTab";
import ExpensesTab from "@/components/property/ExpensesTab";
import AmenitiesTab from "@/components/property/AmenitiesTab";
import AppliancesTab from "@/components/property/AppliancesTab";
import ImprovementsTab from "@/components/property/ImprovementsTab";
import PhotosTab from "@/components/property/PhotosTab";

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
  // Policies
  pets_allowed?: boolean;
  pet_types_allowed?: string | null;
  max_pets?: number | null;
  weight_limit_lbs?: number | null;
  breed_restrictions?: string | null;
  pet_deposit?: string | null;
  pet_rent?: string | null;
  smoking_allowed?: boolean;
  lease_term_months?: number | null;
  available_from?: string | null;
  renters_insurance_required?: boolean;
  renters_insurance_min_coverage?: string | null;
  renters_insurance_required_at_movein?: boolean;
  renters_insurance_notes?: string | null;
  laundry_type?: string | null;
  shared_laundry_location?: string | null;
  shared_laundry_cost?: string | null;
  shared_laundry_notes?: string | null;
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
  { id: "taxes", label: "Taxes" },
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
    if (
      !confirm(
        `Delete "${property?.name}"? It will be hidden but not permanently removed.`
      )
    )
      return;
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
  if (error || !property)
    return <div className="text-red-600">{error || "Not found"}</div>;

  const role = (me?.role || "").toUpperCase();
  const canEdit = role === "ADMIN" || role === "OWNER" || role === "MANAGER";
  const canDelete = role === "ADMIN" || role === "OWNER";

  return (
    <div>
      <Link
        href="/dashboard/properties"
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
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
      {tab === "units" && (
        <UnitsTab units={units} propertyId={propertyId} canEdit={canEdit} />
      )}
      {tab === "history" && <HistoryTab propertyId={propertyId} />}
      {tab === "financials" && (
        <FinancialsTab
          property={property}
          propertyId={propertyId}
          canEdit={canEdit}
        />
      )}
      {tab === "taxes" && (
        <TaxesTab propertyId={propertyId} canEdit={canDelete} />
      )}
      {tab === "policies" && (
        <PoliciesTab
          property={property}
          propertyId={propertyId}
          canEdit={canEdit}
        />
      )}
      {tab === "utilities" && (
        <UtilitiesTab propertyId={propertyId} canEdit={canEdit} />
      )}
      {tab === "insurance" && (
        <InsuranceTab propertyId={propertyId} canEdit={canDelete} />
      )}
      {tab === "expenses" && (
        <ExpensesTab propertyId={propertyId} canEdit={canDelete} />
      )}
      {tab === "amenities" && (
        <AmenitiesTab propertyId={propertyId} canEdit={canEdit} />
      )}
      {tab === "appliances" && (
        <AppliancesTab propertyId={propertyId} canEdit={canEdit} />
      )}
      {tab === "improvements" && (
        <ImprovementsTab propertyId={propertyId} canEdit={canEdit} />
      )}
      {tab === "photos" && (
        <PhotosTab propertyId={propertyId} canEdit={canEdit} />
      )}
      {tab !== "overview" &&
        tab !== "units" &&
        tab !== "history" &&
        tab !== "financials" &&
        tab !== "taxes" &&
        tab !== "policies" &&
        tab !== "utilities" &&
        tab !== "insurance" &&
        tab !== "expenses" &&
        tab !== "amenities" &&
        tab !== "appliances" &&
        tab !== "improvements" &&
        tab !== "photos" && (
          <ComingSoonTab name={TABS.find((t) => t.id === tab)?.label || ""} />
        )}
    </div>
  );
}

function OverviewTab({ property }: { property: Property }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Section title="Basic Information">
        <Row
          label="Property Type"
          value={property.property_type?.replace("_", " ")}
        />
        <Row label="Year Built" value={property.year_built} />
        <Row label="Year Renovated" value={property.year_renovated} />
        <Row
          label="Square Feet"
          value={property.square_feet ? `${property.square_feet} sq ft` : null}
        />
        <Row label="Stories" value={property.stories} />
        <Row
          label="Parking Type"
          value={property.parking_type?.replace("_", " ")}
        />
        <Row label="Parking Spaces" value={property.parking_spaces} />
      </Section>

      <Section title="Financial">
        <Row
          label="Estimated Rent"
          value={
            property.estimated_rent ? `$${property.estimated_rent}/mo` : null
          }
        />
        <Row
          label="Security Deposit"
          value={
            property.security_deposit ? `$${property.security_deposit}` : null
          }
        />
        <Row
          label="Ownership"
          value={property.ownership_status?.replace("_", " ")}
        />
      </Section>

      <Section title="Description" full>
        <p className="text-slate-700 whitespace-pre-wrap">
          {property.description || "No description yet."}
        </p>
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
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  Unit
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  Beds/Baths
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  Sq Ft
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  Rent
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  Status
                </th>
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
                  <td className="px-6 py-4 text-slate-600">
                    {u.bedrooms} bd / {u.bathrooms} ba
                  </td>
                  <td className="px-6 py-4 text-slate-600">
                    {u.square_feet || "—"}
                  </td>
                  <td className="px-6 py-4 text-slate-600">${u.monthly_rent}</td>
                  <td className="px-6 py-4">
                    {u.is_available ? (
                      <span className="text-xs text-green-700 bg-green-50 px-2 py-1 rounded-full">
                        Available
                      </span>
                    ) : (
                      <span className="text-xs text-slate-700 bg-slate-100 px-2 py-1 rounded-full">
                        Occupied
                      </span>
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

type HistoryLog = {
  id: number;
  action: string;
  user_name: string | null;
  created_at: string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
};

function HistoryTab({ propertyId }: { propertyId: number }) {
  const [logs, setLogs] = useState<HistoryLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet(`/properties/${propertyId}/history`)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, [propertyId]);

  if (loading) return <p className="text-slate-500">Loading history…</p>;
  if (logs.length === 0)
    return <p className="text-slate-500">No history yet.</p>;

  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
      {logs.map((log) => (
        <div key={log.id} className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs px-2 py-1 bg-slate-100 text-slate-700 rounded-full uppercase">
                {log.action}
              </span>
              <span className="text-sm text-slate-600">
                {log.user_name || "—"}
              </span>
            </div>
            <span className="text-xs text-slate-500">
              {new Date(log.created_at).toLocaleString()}
            </span>
          </div>
          {log.field_name && (
            <p className="text-sm text-slate-700 mt-2">
              <strong>{log.field_name}</strong>:{" "}
              <span className="text-slate-400">{log.old_value || "—"}</span>
              {" → "}
              <span className="text-slate-900">{log.new_value || "—"}</span>
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

function Section({
  title,
  children,
  full,
}: {
  title: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <div
      className={`bg-white rounded-xl border border-slate-200 p-6 ${
        full ? "md:col-span-2" : ""
      }`}
    >
      <h2 className="font-semibold text-slate-900 mb-4">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Row({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-900 font-medium">{value || "—"}</span>
    </div>
  );
}

// ------------------------------------------------------------
// FINANCIALS TAB
// ------------------------------------------------------------
function FinancialsTab({
  property,
  propertyId,
  canEdit,
}: {
  property: Property & Record<string, unknown>;
  propertyId: number;
  canEdit: boolean;
}) {
  const [taxes, setTaxes] = useState<{ annual_amount: string | null }[]>([]);

  useEffect(() => {
    apiGet(`/properties/${propertyId}/taxes`)
      .then(setTaxes)
      .catch(() => setTaxes([]));
  }, [propertyId]);

  const totalAnnualTax = taxes.reduce(
    (sum, t) => sum + (t.annual_amount ? Number(t.annual_amount) : 0),
    0
  );
  const monthlyTax = totalAnnualTax / 12;

  return (
    <div className="space-y-6">
      {canEdit && (
        <div className="text-right">
          <Link
            href={`/dashboard/properties/${propertyId}/edit`}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            Edit Financials
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Section title="Purchase">
          <Row label="Purchase Date" value={property.purchase_date as string} />
          <Row
            label="Purchase Price"
            value={
              property.purchase_price
                ? `$${Number(property.purchase_price).toLocaleString()}`
                : null
            }
          />
          <Row
            label="Current Market Value"
            value={
              property.current_market_value
                ? `$${Number(property.current_market_value).toLocaleString()}`
                : null
            }
          />
          <Row
            label="Ownership"
            value={property.ownership_status?.replace("_", " ")}
          />
          {property.payoff_date ? (
            <Row label="Payoff Date" value={property.payoff_date as string} />
          ) : null}
          {property.payoff_amount ? (
            <Row
              label="Payoff Amount"
              value={`$${Number(property.payoff_amount).toLocaleString()}`}
            />
          ) : null}
        </Section>

        <Section title="Mortgage">
          <Row label="Lender" value={property.mortgage_lender as string} />
          <Row
            label="Account #"
            value={property.mortgage_account_number as string}
          />
          <Row
            label="Original Amount"
            value={
              property.mortgage_original_amount
                ? `$${Number(
                    property.mortgage_original_amount
                  ).toLocaleString()}`
                : null
            }
          />
          <Row
            label="Current Balance"
            value={
              property.mortgage_current_balance
                ? `$${Number(
                    property.mortgage_current_balance
                  ).toLocaleString()}`
                : null
            }
          />
          <Row
            label="Interest Rate"
            value={
              property.mortgage_interest_rate
                ? `${property.mortgage_interest_rate}%`
                : null
            }
          />
          <Row
            label="Term"
            value={
              property.mortgage_term_months
                ? `${property.mortgage_term_months} months`
                : null
            }
          />
          <Row
            label="Started"
            value={property.mortgage_start_date as string}
          />
          <Row
            label="Monthly Payment"
            value={
              property.mortgage_monthly_payment
                ? `$${Number(
                    property.mortgage_monthly_payment
                  ).toLocaleString()}`
                : null
            }
          />
          <Row
            label="Escrow Included"
            value={property.mortgage_escrow_included ? "Yes" : "No"}
          />
        </Section>

        <Section title="Taxes (summary)" full>
          {taxes.length === 0 ? (
            <p className="text-slate-500 text-sm">
              No tax records yet. Add them in the Taxes tab.
            </p>
          ) : (
            <>
              <Row
                label="Total Annual Tax"
                value={`$${totalAnnualTax.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                })}`}
              />
              <Row
                label="Monthly Equivalent"
                value={`$${monthlyTax.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                })}`}
              />
              <Row label="Tax Authorities" value={taxes.length} />
              <p className="text-xs text-slate-500 mt-4">
                View and manage individual tax records in the{" "}
                <strong>Taxes</strong> tab.
              </p>
            </>
          )}
        </Section>
      </div>
    </div>
  );
}

// ------------------------------------------------------------
// TAXES TAB
// ------------------------------------------------------------
type TaxRecord = {
  id: number;
  property_id: number;
  tax_authority: string;
  tax_type: string;
  parcel_number: string | null;
  assessed_value: string | null;
  tax_rate_percent: string | null;
  annual_amount: string | null;
  payment_frequency: string;
  payment_amount: string | null;
  next_due_date: string | null;
  escrow_included: boolean;
  is_active: boolean;
  notes: string | null;
};

function TaxesTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [taxes, setTaxes] = useState<TaxRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet(`/properties/${propertyId}/taxes`);
      setTaxes(data);
    } catch {
      setTaxes([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  async function handleDelete(id: number) {
    if (!confirm("Delete this tax record?")) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/properties/${propertyId}/taxes/${id}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Delete failed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (loading) return <p className="text-slate-500">Loading…</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-slate-600">
          {taxes.length} tax {taxes.length === 1 ? "record" : "records"}
        </p>
        {canEdit && (
          <button
            onClick={() => {
              setEditingId(null);
              setShowForm(true);
            }}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Tax Record
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {showForm && (
        <TaxForm
          propertyId={propertyId}
          taxId={editingId}
          onCancel={() => {
            setShowForm(false);
            setEditingId(null);
          }}
          onSaved={() => {
            setShowForm(false);
            setEditingId(null);
            load();
          }}
        />
      )}

      {taxes.length === 0 && !showForm ? (
        <p className="text-slate-500">No tax records yet.</p>
      ) : (
        <div className="space-y-4">
          {taxes.map((t) => (
            <div
              key={t.id}
              className="bg-white rounded-xl border border-slate-200 p-6"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-slate-900">
                    {t.tax_authority}
                  </h3>
                  <p className="text-xs text-slate-500 uppercase mt-0.5">
                    {t.tax_type.replace("_", " ")}
                  </p>
                </div>
                {canEdit && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setEditingId(t.id);
                        setShowForm(true);
                      }}
                      className="text-xs px-3 py-1 border border-slate-200 rounded-lg hover:bg-slate-50"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(t.id)}
                      className="text-xs px-3 py-1 border border-red-200 text-red-700 rounded-lg hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-slate-500">Assessed Value</p>
                  <p className="font-medium text-slate-900">
                    {t.assessed_value
                      ? `$${Number(t.assessed_value).toLocaleString()}`
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Tax Rate</p>
                  <p className="font-medium text-slate-900">
                    {t.tax_rate_percent ? `${t.tax_rate_percent}%` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Annual Amount</p>
                  <p className="font-medium text-slate-900">
                    {t.annual_amount
                      ? `$${Number(t.annual_amount).toLocaleString()}`
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Frequency</p>
                  <p className="font-medium text-slate-900">
                    {t.payment_frequency.replace("_", " ")}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Payment Amount</p>
                  <p className="font-medium text-slate-900">
                    {t.payment_amount
                      ? `$${Number(t.payment_amount).toLocaleString()}`
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Next Due</p>
                  <p className="font-medium text-slate-900">
                    {t.next_due_date || "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Escrow</p>
                  <p className="font-medium text-slate-900">
                    {t.escrow_included ? "Yes" : "No"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Parcel #</p>
                  <p className="font-medium text-slate-900">
                    {t.parcel_number || "—"}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// TAX FORM
// ------------------------------------------------------------
function TaxForm({
  propertyId,
  taxId,
  onCancel,
  onSaved,
}: {
  propertyId: number;
  taxId: number | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [taxAuthority, setTaxAuthority] = useState("");
  const [taxType, setTaxType] = useState("county");
  const [parcelNumber, setParcelNumber] = useState("");
  const [assessedValue, setAssessedValue] = useState("");
  const [taxRate, setTaxRate] = useState("");
  const [annualAmount, setAnnualAmount] = useState("");
  const [frequency, setFrequency] = useState("annual");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [nextDueDate, setNextDueDate] = useState("");
  const [escrowIncluded, setEscrowIncluded] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (taxId === null) return;
    apiGet(`/properties/${propertyId}/taxes/${taxId}`).then((t) => {
      setTaxAuthority(t.tax_authority || "");
      setTaxType(t.tax_type || "county");
      setParcelNumber(t.parcel_number || "");
      setAssessedValue(t.assessed_value?.toString() || "");
      setTaxRate(t.tax_rate_percent?.toString() || "");
      setAnnualAmount(t.annual_amount?.toString() || "");
      setFrequency(t.payment_frequency || "annual");
      setPaymentAmount(t.payment_amount?.toString() || "");
      setNextDueDate(t.next_due_date || "");
      setEscrowIncluded(t.escrow_included ?? false);
      setNotes(t.notes || "");
    });
  }, [taxId, propertyId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        tax_authority: taxAuthority,
        tax_type: taxType,
        parcel_number: parcelNumber || null,
        assessed_value: assessedValue ? Number(assessedValue) : null,
        tax_rate_percent: taxRate ? Number(taxRate) : null,
        annual_amount: annualAmount ? Number(annualAmount) : null,
        payment_frequency: frequency,
        payment_amount: paymentAmount ? Number(paymentAmount) : null,
        next_due_date: nextDueDate || null,
        escrow_included: escrowIncluded,
        notes: notes || null,
      };

      const token = localStorage.getItem("token");
      const url = taxId
        ? `http://127.0.0.1:8000/properties/${propertyId}/taxes/${taxId}`
        : `http://127.0.0.1:8000/properties/${propertyId}/taxes`;
      const method = taxId ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Save failed");
      }

      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-xl border border-slate-200 p-6 mb-6 space-y-5"
    >
      <h3 className="font-semibold text-slate-900">
        {taxId ? "Edit Tax Record" : "New Tax Record"}
      </h3>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Tax Authority
          </label>
          <input
            type="text"
            required
            value={taxAuthority}
            onChange={(e) => setTaxAuthority(e.target.value)}
            placeholder="Travis County"
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Tax Type
          </label>
          <select
            value={taxType}
            onChange={(e) => setTaxType(e.target.value)}
            className="input"
          >
            <option value="county">County</option>
            <option value="school">School District</option>
            <option value="municipal">Municipal</option>
            <option value="special_district">Special District</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Parcel #
          </label>
          <input
            type="text"
            value={parcelNumber}
            onChange={(e) => setParcelNumber(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Assessed Value ($)
          </label>
          <input
            type="number"
            step="0.01"
            value={assessedValue}
            onChange={(e) => setAssessedValue(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Tax Rate (%)
          </label>
          <input
            type="number"
            step="0.0001"
            value={taxRate}
            onChange={(e) => setTaxRate(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Annual Amount ($)
          </label>
          <input
            type="number"
            step="0.01"
            value={annualAmount}
            onChange={(e) => setAnnualAmount(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Payment Frequency
          </label>
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            className="input"
          >
            <option value="monthly">Monthly</option>
            <option value="quarterly">Quarterly</option>
            <option value="semi_annual">Semi-Annual</option>
            <option value="annual">Annual</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Payment Amount ($)
          </label>
          <input
            type="number"
            step="0.01"
            value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Next Due Date
          </label>
          <input
            type="date"
            value={nextDueDate}
            onChange={(e) => setNextDueDate(e.target.value)}
            className="input"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="escrow"
          checked={escrowIncluded}
          onChange={(e) => setEscrowIncluded(e.target.checked)}
          className="w-4 h-4"
        />
        <label htmlFor="escrow" className="text-sm text-slate-700">
          Paid from mortgage escrow
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Notes
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="input"
        />
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="bg-slate-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : taxId ? "Update" : "Add Tax Record"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-6 py-2.5 rounded-lg font-medium border border-slate-300 hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ------------------------------------------------------------
// POLICIES TAB
// ------------------------------------------------------------
function PoliciesTab({
  property,
  propertyId,
  canEdit,
}: {
  property: Property;
  propertyId: number;
  canEdit: boolean;
}) {
  const p = property as Property & Record<string, unknown>;

  return (
    <div className="space-y-6">
      {canEdit && (
        <div className="text-right">
          <Link
            href={`/dashboard/properties/${propertyId}/edit#policies`}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            Edit Policies
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Section title="Pets">
          <Row label="Pets Allowed" value={p.pets_allowed ? "Yes" : "No"} />
          {p.pets_allowed ? (
            <>
              <Row
                label="Pet Types Allowed"
                value={p.pet_types_allowed as string}
              />
              <Row label="Max Pets" value={p.max_pets as number} />
              <Row
                label="Weight Limit"
                value={p.weight_limit_lbs ? `${p.weight_limit_lbs} lbs` : null}
              />
              <Row
                label="Breed Restrictions"
                value={p.breed_restrictions as string}
              />
              <Row
                label="Pet Deposit"
                value={
                  p.pet_deposit
                    ? `$${Number(p.pet_deposit).toLocaleString()}`
                    : null
                }
              />
              <Row
                label="Pet Rent"
                value={
                  p.pet_rent
                    ? `$${Number(p.pet_rent).toLocaleString()}/mo`
                    : null
                }
              />
            </>
          ) : null}
        </Section>

        <Section title="Smoking">
          <Row
            label="Smoking Allowed"
            value={p.smoking_allowed ? "Yes" : "No"}
          />
        </Section>

        <Section title="Lease Terms">
          <Row
            label="Standard Lease Term"
            value={
              p.lease_term_months ? `${p.lease_term_months} months` : null
            }
          />
          <Row label="Available From" value={p.available_from as string} />
        </Section>

        <Section title="Tenant Insurance">
          <Row
            label="Required"
            value={p.renters_insurance_required ? "Yes" : "No"}
          />
          {p.renters_insurance_required ? (
            <>
              <Row
                label="Minimum Coverage"
                value={
                  p.renters_insurance_min_coverage
                    ? `$${Number(
                        p.renters_insurance_min_coverage
                      ).toLocaleString()}`
                    : null
                }
              />
              <Row
                label="Required at Move-In"
                value={p.renters_insurance_required_at_movein ? "Yes" : "No"}
              />
              <Row
                label="Notes"
                value={p.renters_insurance_notes as string}
              />
            </>
          ) : null}
        </Section>

        <Section title="Laundry" full>
          <Row
            label="Laundry Type"
            value={(p.laundry_type as string)?.replace("_", " ")}
          />
          {p.laundry_type === "shared_on_site" ? (
            <>
              <Row
                label="Shared Location"
                value={p.shared_laundry_location as string}
              />
              <Row label="Shared Cost" value={p.shared_laundry_cost as string} />
              <Row
                label="Notes"
                value={p.shared_laundry_notes as string}
              />
            </>
          ) : null}
        </Section>
      </div>
    </div>
  );
}