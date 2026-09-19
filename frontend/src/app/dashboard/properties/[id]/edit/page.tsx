"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPatch } from "@/lib/api";
import { PARKING_TYPES } from "@/lib/usStates";
import StateAutocomplete from "@/components/StateAutocomplete";
import AddressAutocomplete, { AddressSuggestion } from "@/components/AddressAutocomplete";

type Me = { role: string };

export default function EditPropertyPage() {
  const params = useParams();
  const router = useRouter();
  const propertyId = Number(params.id);

  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Form fields
  const [name, setName] = useState("");
  const [propertyType, setPropertyType] = useState("multi_family");
  const [addressLine1, setAddressLine1] = useState("");
  const [addressLine2, setAddressLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [yearBuilt, setYearBuilt] = useState("");
  const [yearRenovated, setYearRenovated] = useState("");
  const [squareFeet, setSquareFeet] = useState("");
  const [stories, setStories] = useState("");
  const [parkingSpaces, setParkingSpaces] = useState("");
  const [parkingType, setParkingType] = useState("");
  const [estimatedRent, setEstimatedRent] = useState("");
  const [securityDeposit, setSecurityDeposit] = useState("");
  const [ownershipStatus, setOwnershipStatus] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [meData, prop] = await Promise.all([
          apiGet("/auth/me"),
          apiGet(`/properties/${propertyId}`),
        ]);

        if (meData.role !== "admin" && meData.role !== "owner" && meData.role !== "manager") {
          router.replace(`/dashboard/properties/${propertyId}`);
          return;
        }

        setMe(meData);
        setName(prop.name || "");
        setPropertyType(prop.property_type || "multi_family");
        setAddressLine1(prop.address_line1 || "");
        setAddressLine2(prop.address_line2 || "");
        setCity(prop.city || "");
        setState(prop.state || "");
        setZipCode(prop.zip_code || "");
        setYearBuilt(prop.year_built?.toString() || "");
        setYearRenovated(prop.year_renovated?.toString() || "");
        setSquareFeet(prop.square_feet?.toString() || "");
        setStories(prop.stories?.toString() || "");
        setParkingSpaces(prop.parking_spaces?.toString() || "");
        setParkingType(prop.parking_type || "");
        setEstimatedRent(prop.estimated_rent?.toString() || "");
        setSecurityDeposit(prop.security_deposit?.toString() || "");
        setOwnershipStatus(prop.ownership_status || "");
        setDescription(prop.description || "");
        setNotes(prop.notes || "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [propertyId, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        name,
        property_type: propertyType,
        address_line1: addressLine1,
        address_line2: addressLine2 || null,
        city,
        state,
        zip_code: zipCode,
        year_built: yearBuilt ? Number(yearBuilt) : null,
        year_renovated: yearRenovated ? Number(yearRenovated) : null,
        square_feet: squareFeet ? Number(squareFeet) : null,
        stories: stories ? Number(stories) : null,
        parking_spaces: parkingSpaces ? Number(parkingSpaces) : null,
        parking_type: parkingType || null,
        estimated_rent: estimatedRent ? Number(estimatedRent) : null,
        security_deposit: securityDeposit ? Number(securityDeposit) : null,
        ownership_status: ownershipStatus || null,
        description: description || null,
        notes: notes || null,
      };

      await apiPatch(`/properties/${propertyId}`, body);
      router.push(`/dashboard/properties/${propertyId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;
  if (!me) return <div className="text-red-600">{error || "Not found"}</div>;

  return (
    <div className="max-w-3xl">
      <Link
        href={`/dashboard/properties/${propertyId}`}
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
        ← Back to property
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-6">Edit Property</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-6">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* BASIC INFO */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Basic Information</h2>

          <Field label="Property Name">
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
            />
          </Field>

          <Field label="Property Type">
            <select
              value={propertyType}
              onChange={(e) => setPropertyType(e.target.value)}
              className="input"
            >
              <option value="single_family">Single Family</option>
              <option value="multi_family">Multi-Family</option>
              <option value="apartment">Apartment</option>
              <option value="condo">Condo</option>
              <option value="townhouse">Townhouse</option>
              <option value="commercial">Commercial</option>
              <option value="other">Other</option>
            </select>
          </Field>

          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-3">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Search Address (type to autocomplete)
              </label>
              <AddressAutocomplete
                onSelect={(s: AddressSuggestion) => {
                  setAddressLine1(s.address_line1);
                  setCity(s.city);
                  setState(s.state);
                  setZipCode(s.zip_code);
                }}
                initialValue={addressLine1}
                placeholder="Start typing an address..."
              />
            </div>

            <div className="col-span-3">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Address Line 1
              </label>
              <input
                type="text"
                required
                value={addressLine1}
                onChange={(e) => setAddressLine1(e.target.value)}
                className="input"
              />
            </div>

            <div className="col-span-3">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Address Line 2 (optional)
              </label>
              <input
                type="text"
                value={addressLine2}
                onChange={(e) => setAddressLine2(e.target.value)}
                className="input"
              />
            </div>

            <div className="col-span-1">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                City
              </label>
              <input
                type="text"
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                State
              </label>
              <StateAutocomplete value={state} onChange={setState} />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Zip
              </label>
              <input
                type="text"
                required
                value={zipCode}
                onChange={(e) => setZipCode(e.target.value)}
                className="input"
              />
            </div>
          </div>
        </div>

        {/* PHYSICAL */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Physical Details</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Year Built
              </label>
              <input
                type="number"
                value={yearBuilt}
                onChange={(e) => setYearBuilt(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Year Renovated
              </label>
              <input
                type="number"
                value={yearRenovated}
                onChange={(e) => setYearRenovated(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Square Feet
              </label>
              <input
                type="number"
                value={squareFeet}
                onChange={(e) => setSquareFeet(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Stories
              </label>
              <input
                type="number"
                value={stories}
                onChange={(e) => setStories(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Parking Type
              </label>
              <select
                value={parkingType}
                onChange={(e) => setParkingType(e.target.value)}
                className="input"
              >
                <option value="">— Select —</option>
                {PARKING_TYPES.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            {parkingType && parkingType !== "none" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Parking Spaces
                </label>
                <input
                  type="number"
                  min="0"
                  placeholder="Leave blank if unknown"
                  value={parkingSpaces}
                  onChange={(e) => setParkingSpaces(e.target.value)}
                  className="input"
                />
              </div>
            )}
          </div>
        </div>

        {/* FINANCIAL */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Financial</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Estimated Rent ($/month)
              </label>
              <input
                type="number"
                step="0.01"
                value={estimatedRent}
                onChange={(e) => setEstimatedRent(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Security Deposit ($)
              </label>
              <input
                type="number"
                step="0.01"
                value={securityDeposit}
                onChange={(e) => setSecurityDeposit(e.target.value)}
                className="input"
              />
            </div>
          </div>

          <Field label="Ownership Status">
            <select
              value={ownershipStatus}
              onChange={(e) => setOwnershipStatus(e.target.value)}
              className="input"
            >
              <option value="">— Select —</option>
              <option value="owned_outright">Owned Outright</option>
              <option value="mortgaged">Mortgaged</option>
              <option value="renting">Renting</option>
              <option value="other">Other</option>
            </select>
          </Field>
        </div>

        {/* DESCRIPTION */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Description</h2>

          <Field label="Public Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              placeholder="Marketing description for listings..."
              className="input"
            />
          </Field>

          <Field label="Internal Notes (not shown to tenants)">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Private notes about this property..."
              className="input"
            />
          </Field>
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="bg-slate-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
          <Link
            href={`/dashboard/properties/${propertyId}`}
            className="px-6 py-2.5 rounded-lg font-medium border border-slate-300 hover:bg-slate-50"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      {children}
    </div>
  );
}