"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost, apiGet } from "@/lib/api";

type Me = {
  role: string;
  organization_id: number | null;
};

export default function AddPersonPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  // Form fields
  const [role, setRole] = useState("manager");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const meData = await apiGet("/auth/me");
        setMe(meData);
        if (meData.role === "crew" || meData.role === "tenant") {
          router.replace("/dashboard/team");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  function rolesAvailable(): { value: string; label: string }[] {
    if (!me) return [];
    if (me.role === "admin") {
      return [
        { value: "owner", label: "Owner" },
        { value: "manager", label: "Manager" },
        { value: "crew", label: "Crew" },
        { value: "tenant", label: "Tenant" },
      ];
    }
    if (me.role === "owner") {
      return [
        { value: "manager", label: "Manager" },
        { value: "crew", label: "Crew" },
        { value: "tenant", label: "Tenant" },
      ];
    }
    if (me.role === "manager") {
      return [
        { value: "crew", label: "Crew" },
        { value: "tenant", label: "Tenant" },
      ];
    }
    return [];
  }

  function endpointForRole(r: string): string {
    switch (r) {
      case "owner":
        return "/users/owners";
      case "manager":
        return "/users/managers";
      case "crew":
        return "/users/crew";
      case "tenant":
        return "/users/tenants";
      default:
        throw new Error("Unknown role");
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      if (!me) throw new Error("Not loaded");

      const body: Record<string, unknown> = {
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        phone: phone || null,
        role,
      };

      // Admin must specify an organization_id
      if (me.role === "admin" && me.organization_id === null) {
        // For now, default admin-created users to org 1
        // (In a fuller version, we'd add an org-picker)
        body.organization_id = 1;
      } else if (me.organization_id !== null) {
        body.organization_id = me.organization_id;
      }

      await apiPost(endpointForRole(role), body);
      router.push("/dashboard/team");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="max-w-xl">
      <Link
        href="/dashboard/team"
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
        ← Back to team
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-6">Add a Person</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-6">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-xl border border-slate-200 p-6 space-y-5"
      >
        {/* Role */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Role
          </label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 bg-white"
          >
            {rolesAvailable().map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        {/* Name */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              First Name
            </label>
            <input
              type="text"
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Last Name
            </label>
            <input
              type="text"
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
            />
          </div>
        </div>

        {/* Email */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email
          </label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        {/* Phone */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Phone (optional)
          </label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        {/* Password */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Temporary Password
          </label>
          <input
            type="text"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
          <p className="text-xs text-slate-500 mt-1">
            Share this with them securely. They can change it after logging in.
          </p>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-slate-900 text-white py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Creating…" : "Create Person"}
        </button>
      </form>
    </div>
  );
}