"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPatch, apiPost, fileUrl } from "@/lib/api";

type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  profile_photo_url: string | null;
};

type Me = { id: number; role: string };

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  owner: "Owner",
  manager: "Manager",
  crew: "Crew",
  tenant: "Tenant",
};

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = Number(params.id);

  const [me, setMe] = useState<Me | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [meData, userData] = await Promise.all([
          apiGet("/auth/me"),
          apiGet(`/users/${userId}`),
        ]);
        setMe(meData);
        setUser(userData);
        setFirstName(userData.first_name);
        setLastName(userData.last_name);
        setPhone(userData.phone || "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [userId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const updated = await apiPatch(`/users/${user.id}`, {
        first_name: firstName,
        last_name: lastName,
        phone: phone || null,
      });
      setUser(updated);
      setSuccess("Saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleResetPassword() {
    if (!user) return;
    if (!confirm(`Send password reset link to ${user.email}?`)) return;
    setError("");
    setSuccess("");
    try {
      const result = await apiPost(`/users/${user.id}/force-reset`);
      setSuccess(result.detail || "Reset link sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  async function handleDeactivate() {
    if (!user) return;
    if (!confirm(`Deactivate ${user.first_name} ${user.last_name}?`)) return;
    setError("");
    setSuccess("");
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://127.0.0.1:8000/users/${user.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Deactivate failed");
      router.push("/dashboard/team");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deactivate failed");
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;
  if (!user) return <div className="text-red-600">{error || "Not found"}</div>;

  const canManage =
    me?.role === "admin" || me?.role === "owner" || me?.role === "manager";
  const isSelf = me?.id === user.id;

  return (
    <div className="max-w-xl">
      <Link
        href="/dashboard/team"
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
        ← Back to team
      </Link>

      <div className="flex items-center gap-4 mb-6">
        {user.profile_photo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={fileUrl(user.profile_photo_url)}
            alt={user.first_name}
            className="w-16 h-16 rounded-full object-cover border border-slate-200"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-slate-900 text-white flex items-center justify-center text-xl font-medium">
            {user.first_name.charAt(0).toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {user.first_name} {user.last_name}
          </h1>
          <p className="text-slate-500 text-sm">{user.email}</p>
          <span className="inline-block mt-1 text-xs px-2 py-0.5 bg-slate-100 text-slate-700 rounded-full uppercase tracking-wide">
            {ROLE_LABELS[user.role] || user.role}
          </span>
          {!user.is_active && (
            <span className="inline-block mt-1 ml-2 text-xs px-2 py-0.5 bg-red-50 text-red-700 rounded-full">
              Inactive
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-6">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3 mb-6">
          {success}
        </div>
      )}

      {(canManage || isSelf) && (
        <form
          onSubmit={handleSave}
          className="bg-white rounded-xl border border-slate-200 p-6 space-y-5 mb-6"
        >
          <h2 className="font-semibold text-slate-900">Details</h2>

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

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Phone
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="bg-slate-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </form>
      )}

      {canManage && !isSelf && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-3">
          <h2 className="font-semibold text-slate-900">Admin Actions</h2>

          <button
            onClick={handleResetPassword}
            className="w-full text-left px-4 py-3 border border-slate-200 rounded-lg hover:bg-slate-50 text-sm"
          >
            <span className="font-medium text-slate-900">Send password reset link</span>
            <span className="block text-xs text-slate-500 mt-0.5">
              Emails {user.email} a link to set a new password.
            </span>
          </button>

          {user.is_active && (
            <button
              onClick={handleDeactivate}
              className="w-full text-left px-4 py-3 border border-red-200 rounded-lg hover:bg-red-50 text-sm"
            >
              <span className="font-medium text-red-700">Deactivate this person</span>
              <span className="block text-xs text-red-500 mt-0.5">
                They won&apos;t be able to log in. This doesn&apos;t delete their data.
              </span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}