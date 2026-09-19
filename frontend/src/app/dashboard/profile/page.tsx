// ============================================================
// Profile Page
// ------------------------------------------------------------
// Any logged-in user can view/edit their profile and upload a
// profile photo.
// ============================================================

"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPatch, apiUpload, fileUrl } from "@/lib/api";

type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: string;
  profile_photo_url: string | null;
};

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const me: User = await apiGet("/auth/me");
        setUser(me);
        setFirstName(me.first_name);
        setLastName(me.last_name);
        setPhone(me.phone || "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const updated: User = await apiPatch(`/users/${user.id}`, {
        first_name: firstName,
        last_name: lastName,
        phone: phone || null,
      });
      setUser(updated);
      setSuccess("Profile updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handlePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !user) return;

    setError("");
    setSuccess("");
    setUploading(true);
    try {
      const result = await apiUpload(file);
      const updated: User = await apiPatch(`/users/${user.id}`, {
        profile_photo_url: result.url,
      });
      setUser(updated);
      setSuccess("Photo updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;
  if (!user) return <div className="text-red-600">{error || "Not found"}</div>;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">My Profile</h1>

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

      {/* Photo */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
        <h2 className="font-semibold text-slate-900 mb-4">Profile Photo</h2>
        <div className="flex items-center gap-6">
          <div className="w-24 h-24 rounded-full bg-slate-100 flex items-center justify-center overflow-hidden border border-slate-200">
            {user.profile_photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={fileUrl(user.profile_photo_url)}
                alt="Profile"
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-3xl text-slate-400">
                {user.first_name.charAt(0).toUpperCase()}
              </span>
            )}
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handlePhotoChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 bg-slate-900 text-white rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50 text-sm"
            >
              {uploading ? "Uploading…" : "Upload Photo"}
            </button>
            <p className="text-xs text-slate-500 mt-2">
              JPG, PNG, or WebP. Max 10 MB.
            </p>
          </div>
        </div>
      </div>

      {/* Details */}
      <form
        onSubmit={handleSave}
        className="bg-white rounded-xl border border-slate-200 p-6 space-y-4"
      >
        <h2 className="font-semibold text-slate-900">Details</h2>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email
          </label>
          <input
            type="email"
            value={user.email}
            disabled
            className="w-full px-4 py-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-500"
          />
          <p className="text-xs text-slate-500 mt-1">
            Email cannot be changed here.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            First Name
          </label>
          <input
            type="text"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Last Name
          </label>
          <input
            type="text"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Phone
          </label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="(555) 555-5555"
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
    </div>
  );
}