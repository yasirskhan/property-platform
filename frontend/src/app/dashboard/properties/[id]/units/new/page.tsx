"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost, apiGet } from "@/lib/api";

export default function AddUnitPage() {
  const params = useParams();
  const router = useRouter();
  const propertyId = Number(params.id);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [planLimitReached, setPlanLimitReached] = useState(false);
  const [propertyName, setPropertyName] = useState("");

  const [unitNumber, setUnitNumber] = useState("");
  const [bedrooms, setBedrooms] = useState("1");
  const [bathrooms, setBathrooms] = useState("1");
  const [squareFeet, setSquareFeet] = useState("");
  const [monthlyRent, setMonthlyRent] = useState("");
  const [securityDeposit, setSecurityDeposit] = useState("");
  const [petDeposit, setPetDeposit] = useState("");
  const [petRent, setPetRent] = useState("");
  const [applicationFee, setApplicationFee] = useState("");
  const [adminFee, setAdminFee] = useState("");
  const [availableFrom, setAvailableFrom] = useState("");
  const [leaseTermMonths, setLeaseTermMonths] = useState("12");
  const [isListed, setIsListed] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [me, prop] = await Promise.all([
          apiGet("/auth/me"),
          apiGet(`/properties/${propertyId}`),
        ]);
        if (me.role !== "admin" && me.role !== "owner" && me.role !== "manager") {
          router.replace(`/dashboard/properties/${propertyId}`);
          return;
        }
        setPropertyName(prop.name);
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
    setPlanLimitReached(false);
    setSaving(true);
    try {
      await apiPost(`/properties/${propertyId}/units`, {
        unit_number: unitNumber,
        bedrooms: Number(bedrooms),
        bathrooms: Number(bathrooms),
        square_feet: squareFeet ? Number(squareFeet) : null,
        monthly_rent: Number(monthlyRent),
        security_deposit: securityDeposit ? Number(securityDeposit) : null,
        pet_deposit: petDeposit ? Number(petDeposit) : null,
        pet_rent: petRent ? Number(petRent) : null,
        application_fee: applicationFee ? Number(applicationFee) : null,
        admin_fee: adminFee ? Number(adminFee) : null,
        available_from: availableFrom || null,
        lease_term_months: leaseTermMonths ? Number(leaseTermMonths) : null,
        is_listed: isListed,
      });
      router.push(`/dashboard/properties/${propertyId}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Save failed";
      const prefix = "PLAN_UNIT_LIMIT_REACHED:";
      if (message.startsWith(prefix)) {
        setPlanLimitReached(true);
        setError(message.slice(prefix.length).trim());
      } else {
        setError(message);
      }
      setSaving(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="max-w-2xl">
      <Link
        href={`/dashboard/properties/${propertyId}`}
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
        ← Back to {propertyName || "property"}
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-6">Add Unit</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-6">
          <p>{error}</p>
          {planLimitReached && (
            <Link
              href="/signup?upgrade=units"
              className="mt-2 inline-block font-medium underline underline-offset-2"
            >
              Review plan options
            </Link>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Unit Details</h2>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Unit Number</label>
            <input
              type="text"
              required
              value={unitNumber}
              onChange={(e) => setUnitNumber(e.target.value)}
              placeholder="101, A, 2B"
              className="input"
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Bedrooms</label>
              <input
                type="number"
                min="0"
                value={bedrooms}
                onChange={(e) => setBedrooms(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Bathrooms</label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={bathrooms}
                onChange={(e) => setBathrooms(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Sq Ft</label>
              <input
                type="number"
                value={squareFeet}
                onChange={(e) => setSquareFeet(e.target.value)}
                className="input"
              />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Rent & Fees</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Monthly Rent ($)</label>
              <input
                type="number"
                required
                step="0.01"
                value={monthlyRent}
                onChange={(e) => setMonthlyRent(e.target.value)}
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
              <label className="block text-sm font-medium text-slate-700 mb-1">Pet Deposit ($)</label>
              <input
                type="number"
                step="0.01"
                value={petDeposit}
                onChange={(e) => setPetDeposit(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Pet Rent ($/mo)</label>
              <input
                type="number"
                step="0.01"
                value={petRent}
                onChange={(e) => setPetRent(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Application Fee ($)</label>
              <input
                type="number"
                step="0.01"
                value={applicationFee}
                onChange={(e) => setApplicationFee(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Admin Fee ($)</label>
              <input
                type="number"
                step="0.01"
                value={adminFee}
                onChange={(e) => setAdminFee(e.target.value)}
                className="input"
              />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
          <h2 className="font-semibold text-slate-900">Availability</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Available From</label>
              <input
                type="date"
                value={availableFrom}
                onChange={(e) => setAvailableFrom(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Lease Term (months)</label>
              <input
                type="number"
                value={leaseTermMonths}
                onChange={(e) => setLeaseTermMonths(e.target.value)}
                className="input"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="listed"
              checked={isListed}
              onChange={(e) => setIsListed(e.target.checked)}
              className="w-4 h-4"
            />
            <label htmlFor="listed" className="text-sm text-slate-700">
              List this unit publicly (show on website)
            </label>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="bg-slate-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
          >
            {saving ? "Creating…" : "Create Unit"}
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