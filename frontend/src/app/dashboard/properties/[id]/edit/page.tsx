"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPatch } from "@/lib/api";
import { PARKING_TYPES } from "@/lib/usStates";
import StateAutocomplete from "@/components/StateAutocomplete";
import AddressAutocomplete, { AddressSuggestion } from "@/components/AddressAutocomplete";
import { useDisplay } from "@/contexts/DisplayContext";

type Me = { role: string };

export default function EditPropertyPage() {
  const { prefs } = useDisplay();
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
  const [requiredReserveAmount, setRequiredReserveAmount] = useState("");
  const [ownershipStatus, setOwnershipStatus] = useState("");
  const [petsAllowed, setPetsAllowed] = useState(false);
  const [petTypesAllowed, setPetTypesAllowed] = useState("");
  const [maxPets, setMaxPets] = useState("");
  const [weightLimit, setWeightLimit] = useState("");
  const [breedRestrictions, setBreedRestrictions] = useState("");
  const [petDeposit, setPetDeposit] = useState("");
  const [petRent, setPetRent] = useState("");
  const [smokingAllowed, setSmokingAllowed] = useState(false);
  const [leaseTermMonths, setLeaseTermMonths] = useState("");
  const [availableFrom, setAvailableFrom] = useState("");
  const [rentersInsuranceRequired, setRentersInsuranceRequired] = useState(false);
  const [rentersInsuranceMinCoverage, setRentersInsuranceMinCoverage] = useState("");
  const [rentersInsuranceAtMovein, setRentersInsuranceAtMovein] = useState(false);
  const [rentersInsuranceNotes, setRentersInsuranceNotes] = useState("");
  const [laundryType, setLaundryType] = useState("");
  const [sharedLaundryLocation, setSharedLaundryLocation] = useState("");
  const [sharedLaundryCost, setSharedLaundryCost] = useState("");
  const [sharedLaundryNotes, setSharedLaundryNotes] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [meData, prop] = await Promise.all([
          apiGet("/auth/me"),
          apiGet(`/properties/${propertyId}`),
        ]);

        const role = String(meData.role || "").toUpperCase();
        if (role !== "ADMIN" && role !== "OWNER") {
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
        setRequiredReserveAmount(prop.required_reserve_amount?.toString() || "0");
        setOwnershipStatus(prop.ownership_status || "");
        setPetsAllowed(prop.pets_allowed ?? false);
        setPetTypesAllowed(prop.pet_types_allowed || "");
        setMaxPets(prop.max_pets?.toString() || "");
        setWeightLimit(prop.weight_limit_lbs?.toString() || "");
        setBreedRestrictions(prop.breed_restrictions || "");
        setPetDeposit(prop.pet_deposit?.toString() || "");
        setPetRent(prop.pet_rent?.toString() || "");
        setSmokingAllowed(prop.smoking_allowed ?? false);
        setLeaseTermMonths(prop.lease_term_months?.toString() || "");
        setAvailableFrom(prop.available_from || "");
        setRentersInsuranceRequired(prop.renters_insurance_required ?? false);
        setRentersInsuranceMinCoverage(prop.renters_insurance_min_coverage?.toString() || "");
        setRentersInsuranceAtMovein(prop.renters_insurance_required_at_movein ?? false);
        setRentersInsuranceNotes(prop.renters_insurance_notes || "");
        setLaundryType(prop.laundry_type || "");
        setSharedLaundryLocation(prop.shared_laundry_location || "");
        setSharedLaundryCost(prop.shared_laundry_cost || "");
        setSharedLaundryNotes(prop.shared_laundry_notes || "");
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
        required_reserve_amount: requiredReserveAmount ? Number(requiredReserveAmount) : 0,
        ownership_status: ownershipStatus || null,
        description: description || null,
        notes: notes || null,
        pets_allowed: petsAllowed,
        pet_types_allowed: petTypesAllowed || null,
        max_pets: maxPets ? Number(maxPets) : null,
        weight_limit_lbs: weightLimit ? Number(weightLimit) : null,
        breed_restrictions: breedRestrictions || null,
        pet_deposit: petDeposit ? Number(petDeposit) : null,
        pet_rent: petRent ? Number(petRent) : null,
        smoking_allowed: smokingAllowed,
        lease_term_months: leaseTermMonths ? Number(leaseTermMonths) : null,
        available_from: availableFrom || null,
        renters_insurance_required: rentersInsuranceRequired,
        renters_insurance_min_coverage: rentersInsuranceMinCoverage ? Number(rentersInsuranceMinCoverage) : null,
        renters_insurance_required_at_movein: rentersInsuranceAtMovein,
        renters_insurance_notes: rentersInsuranceNotes || null,
        laundry_type: laundryType || null,
        shared_laundry_location: sharedLaundryLocation || null,
        shared_laundry_cost: sharedLaundryCost || null,
        shared_laundry_notes: sharedLaundryNotes || null,
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
    <div
      className="max-w-3xl"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
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

          <Field label="Required Owner Reserve ($)">
            <input
              type="number"
              min="0"
              step="0.01"
              value={requiredReserveAmount}
              onChange={(e) => setRequiredReserveAmount(e.target.value)}
              className="input"
            />
            <p className="text-xs text-slate-500 mt-1">
              Minimum property cash to retain before owner distributions.
            </p>
          </Field>

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

        {/* POLICIES */}
        <div id="policies" className="scroll-mt-4 bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Policies</h2>

          {/* Pets */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="petsAllowed"
              checked={petsAllowed}
              onChange={(e) => setPetsAllowed(e.target.checked)}
              className="w-4 h-4"
            />
            <label htmlFor="petsAllowed" className="text-sm text-slate-700 font-medium">
              Pets Allowed
            </label>
          </div>

          {petsAllowed && (
            <div className="grid grid-cols-2 gap-4 pl-7">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Pet Types Allowed</label>
                <select value={petTypesAllowed} onChange={(e) => setPetTypesAllowed(e.target.value)} className="input">
                  <option value="">— Select —</option>
                  <option value="cats">Cats</option>
                  <option value="dogs">Dogs</option>
                  <option value="both">Both</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Max Pets</label>
                <input type="number" min="0" value={maxPets} onChange={(e) => setMaxPets(e.target.value)} className="input" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Weight Limit (lbs)</label>
                <input type="number" min="0" value={weightLimit} onChange={(e) => setWeightLimit(e.target.value)} className="input" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Pet Deposit ($)</label>
                <input type="number" step="0.01" value={petDeposit} onChange={(e) => setPetDeposit(e.target.value)} className="input" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Pet Rent ($/mo)</label>
                <input type="number" step="0.01" value={petRent} onChange={(e) => setPetRent(e.target.value)} className="input" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">Breed Restrictions</label>
                <textarea value={breedRestrictions} onChange={(e) => setBreedRestrictions(e.target.value)} rows={2} className="input" />
              </div>
            </div>
          )}

          <hr className="border-slate-100" />

          {/* Smoking */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="smokingAllowed"
              checked={smokingAllowed}
              onChange={(e) => setSmokingAllowed(e.target.checked)}
              className="w-4 h-4"
            />
            <label htmlFor="smokingAllowed" className="text-sm text-slate-700 font-medium">
              Smoking Allowed
            </label>
          </div>

          <hr className="border-slate-100" />

          {/* Lease terms */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Lease Term (months)</label>
              <input type="number" value={leaseTermMonths} onChange={(e) => setLeaseTermMonths(e.target.value)} className="input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Available From</label>
              <input type="date" value={availableFrom} onChange={(e) => setAvailableFrom(e.target.value)} className="input" />
            </div>
          </div>

          <hr className="border-slate-100" />

          {/* Tenant Insurance */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <input
                type="checkbox"
                id="rentersInsurance"
                checked={rentersInsuranceRequired}
                onChange={(e) => setRentersInsuranceRequired(e.target.checked)}
                className="w-4 h-4"
              />
              <label htmlFor="rentersInsurance" className="text-sm text-slate-700 font-medium">
                Renters Insurance Required
              </label>
            </div>

            {rentersInsuranceRequired && (
              <div className="grid grid-cols-2 gap-4 pl-7">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Minimum Coverage ($)
                  </label>
                  <input type="number" step="0.01" value={rentersInsuranceMinCoverage} onChange={(e) => setRentersInsuranceMinCoverage(e.target.value)} className="input" />
                </div>
                <div className="flex items-end">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      id="reqMovein"
                      checked={rentersInsuranceAtMovein}
                      onChange={(e) => setRentersInsuranceAtMovein(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <label htmlFor="reqMovein" className="text-sm text-slate-700">
                      Required at move-in
                    </label>
                  </div>
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-slate-700 mb-1">Insurance Notes</label>
                  <textarea value={rentersInsuranceNotes} onChange={(e) => setRentersInsuranceNotes(e.target.value)} rows={2} className="input" />
                </div>
              </div>
            )}
          </div>

          <hr className="border-slate-100" />

          {/* Laundry */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Laundry</label>
            <select value={laundryType} onChange={(e) => setLaundryType(e.target.value)} className="input">
              <option value="">— Select —</option>
              <option value="in_unit">In-Unit</option>
              <option value="shared_on_site">Shared (On Site)</option>
              <option value="hookups_only">Hookups Only</option>
              <option value="none">None</option>
            </select>
          </div>

          {laundryType === "shared_on_site" && (
            <div className="grid grid-cols-2 gap-4 pl-4">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">Shared Laundry Location</label>
                <input type="text" value={sharedLaundryLocation} onChange={(e) => setSharedLaundryLocation(e.target.value)} placeholder="Basement, 2nd floor, etc." className="input" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">Cost</label>
                <input type="text" value={sharedLaundryCost} onChange={(e) => setSharedLaundryCost(e.target.value)} placeholder="Free, $2.00/wash, etc." className="input" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
                <textarea value={sharedLaundryNotes} onChange={(e) => setSharedLaundryNotes(e.target.value)} rows={2} className="input" />
              </div>
            </div>
          )}
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