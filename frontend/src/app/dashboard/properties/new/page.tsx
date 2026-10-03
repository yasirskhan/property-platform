"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost, apiGet } from "@/lib/api";
import { PARKING_TYPES } from "@/lib/usStates";
import StateAutocomplete from "@/components/StateAutocomplete";
import AddressAutocomplete, { AddressSuggestion } from "@/components/AddressAutocomplete";
import { useDisplay } from "@/contexts/DisplayContext";

type Me = {
  role: string;
  organization_id: number | null;
};

export default function AddPropertyPage() {
  const router = useRouter();
  const { prefs } = useDisplay();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

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
        const meData = await apiGet("/auth/me");
        setMe(meData);
        const role = String(meData.role || "").toUpperCase();
        if (role !== "ADMIN" && role !== "OWNER") {
          router.replace("/dashboard/properties");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      if (!me) throw new Error("Not loaded");
      if (!me.organization_id) {
        throw new Error("Your account isn't linked to an organization");
      }

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
        organization_id: me.organization_id,
      };

      const created = await apiPost("/properties", body);
      router.push(`/dashboard/properties/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div
      className="max-w-2xl"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <Link
        href="/dashboard/properties"
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
        ← Back to properties
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-6">Add a Property</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-6">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Property Name</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Oak Street Apartments"
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Property Type</label>
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
        </div>

        <div>
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
            placeholder="Start typing an address..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Address Line 1
          </label>
          <input
            type="text"
            required
            value={addressLine1}
            onChange={(e) => setAddressLine1(e.target.value)}
            placeholder="123 Oak Street"
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Address Line 2 (optional)</label>
          <input
            type="text"
            value={addressLine2}
            onChange={(e) => setAddressLine2(e.target.value)}
            placeholder="Apt, Suite, etc."
            className="input"
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-1">
            <label className="block text-sm font-medium text-slate-700 mb-1">City</label>
            <input
              type="text"
              required
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">State</label>
            <StateAutocomplete value={state} onChange={setState} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Zip</label>
            <input
              type="text"
              required
              value={zipCode}
              onChange={(e) => setZipCode(e.target.value)}
              placeholder="78701"
              className="input"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Year Built</label>
            <input
              type="number"
              value={yearBuilt}
              onChange={(e) => setYearBuilt(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Year Renovated</label>
            <input
              type="number"
              value={yearRenovated}
              onChange={(e) => setYearRenovated(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Stories</label>
            <input
              type="number"
              value={stories}
              onChange={(e) => setStories(e.target.value)}
              className="input"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Square Feet</label>
            <input
              type="number"
              value={squareFeet}
              onChange={(e) => setSquareFeet(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Parking Type</label>
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
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1"># Spaces</label>
            <input
              type="number"
              value={parkingSpaces}
              onChange={(e) => setParkingSpaces(e.target.value)}
              className="input"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Estimated Rent ($/mo)</label>
            <input
              type="number"
              step="0.01"
              value={estimatedRent}
              onChange={(e) => setEstimatedRent(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Security Deposit ($)</label>
            <input
              type="number"
              step="0.01"
              value={securityDeposit}
              onChange={(e) => setSecurityDeposit(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Ownership</label>
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
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Internal Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="input"
          />
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-slate-900 text-white py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Creating…" : "Create Property"}
        </button>
      </form>
    </div>
  );
}