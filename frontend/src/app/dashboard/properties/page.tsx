"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

type Property = {
  id: number;
  name: string;
  property_type: string;
  address_line1: string;
  city: string;
  state: string;
  zip_code: string;
  is_active: boolean;
};

type Me = { role: string };

const TYPE_LABELS: Record<string, string> = {
  single_family: "Single Family",
  multi_family: "Multi-Family",
  apartment: "Apartment",
  condo: "Condo",
  townhouse: "Townhouse",
  commercial: "Commercial",
  other: "Other",
};

export default function PropertiesPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const meData = await apiGet("/auth/me");
        setMe(meData);

        if (meData.role === "crew" || meData.role === "tenant") {
          setError("You don't have access to properties.");
          setLoading(false);
          return;
        }

        const data = await apiGet("/properties");
        setProperties(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;

  const canCreate = me?.role === "admin" || me?.role === "owner";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Properties</h1>
          <p className="text-slate-500 mt-1">
            {properties.length}{" "}
            {properties.length === 1 ? "property" : "properties"}
          </p>
        </div>
        {canCreate && (
          <Link
            href="/dashboard/properties/new"
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Property
          </Link>
        )}
      </div>

      {properties.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-500 mb-4">No properties yet.</p>
          {canCreate && (
            <Link
              href="/dashboard/properties/new"
              className="inline-block px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 text-sm"
            >
              Add your first property
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {properties.map((p) => (
            <Link
              key={p.id}
              href={`/dashboard/properties/${p.id}`}
              className="block bg-white rounded-xl border border-slate-200 p-6 hover:border-slate-400 hover:shadow-sm transition"
            >
              <div className="flex items-start justify-between mb-3">
                <span className="text-xs px-2 py-1 bg-slate-100 text-slate-700 rounded-full uppercase tracking-wide">
                  {TYPE_LABELS[p.property_type] || p.property_type}
                </span>
                {!p.is_active && (
                  <span className="text-xs px-2 py-1 bg-red-50 text-red-700 rounded-full">
                    Inactive
                  </span>
                )}
              </div>
              <h2 className="font-semibold text-slate-900 text-lg mb-2">
                {p.name}
              </h2>
              <p className="text-sm text-slate-600">{p.address_line1}</p>
              <p className="text-sm text-slate-500">
                {p.city}, {p.state} {p.zip_code}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}