"use client";

import { useEffect, useRef, useState } from "react";

import {
  apiGet,
  apiPatch,
  apiPost,
  apiUpload,
  fileUrl,
} from "@/lib/api";
import {
  getMySettings,
  updateMySettings,
  type MySettingsUpdate,
} from "@/lib/mySettings";

type TwoFactorStatus = { enabled: boolean; recovery_codes_remaining: number; verified_at: string | null };
type TwoFactorSetup = { secret: string; otpauth_uri: string; recovery_codes: string[] };

type CurrentUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: string;
  profile_photo_url: string | null;
};

export default function MySettingsPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [prefs, setPrefs] = useState<MySettingsUpdate | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [twoFactorStatus, setTwoFactorStatus] = useState<TwoFactorStatus | null>(null);
  const [twoFactorPassword, setTwoFactorPassword] = useState("");
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [twoFactorSetup, setTwoFactorSetup] = useState<TwoFactorSetup | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([apiGet("/auth/me"), getMySettings(), apiGet("/api/settings/my/two-factor")])
      .then(([me, settings, security]) => {
        const current = me as CurrentUser;
        setUser(current);
        setFirstName(current.first_name);
        setLastName(current.last_name);
        setPhone(current.phone || "");
        setTwoFactorStatus(security as TwoFactorStatus);
        setPrefs({
          email_notifications_enabled: settings.email_notifications_enabled,
          email_signature: settings.email_signature,
          reply_to_email: settings.reply_to_email,
          language_override: settings.language_override,
          export_format_override: settings.export_format_override,
        });
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load My Settings.")
      )
      .finally(() => setLoading(false));
  }, []);

  function begin(name: string) {
    setBusy(name);
    setError("");
    setMessage("");
  }

  function finish() {
    setBusy("");
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!user) return;
    begin("profile");
    try {
      const updated = (await apiPatch("/users/" + user.id, {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim() || null,
      })) as CurrentUser;
      setUser(updated);
      setFirstName(updated.first_name);
      setLastName(updated.last_name);
      setPhone(updated.phone || "");
      setMessage("Profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile.");
    } finally {
      finish();
    }
  }

  async function uploadPhoto(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !user) return;
    begin("photo");
    try {
      const upload = await apiUpload(file);
      const updated = (await apiPatch("/users/" + user.id, {
        profile_photo_url: upload.url,
      })) as CurrentUser;
      setUser(updated);
      setMessage("Profile photo saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile photo.");
    } finally {
      finish();
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function savePreferences(event: React.FormEvent) {
    event.preventDefault();
    if (!prefs) return;
    begin("preferences");
    try {
      const updated = await updateMySettings(prefs);
      setPrefs({
        email_notifications_enabled: updated.email_notifications_enabled,
        email_signature: updated.email_signature,
        reply_to_email: updated.reply_to_email,
        language_override: updated.language_override,
        export_format_override: updated.export_format_override,
      });
      setMessage("Personal preferences saved.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not save personal preferences."
      );
    } finally {
      finish();
    }
  }

  async function changePassword(event: React.FormEvent) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }
    begin("password");
    try {
      await apiPost("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("Password updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update password.");
    } finally {
      finish();
    }
  }

  async function startTwoFactorSetup() {
    begin("two-factor-setup");
    try {
      const setup = (await apiPost("/api/settings/my/two-factor/setup", {
        current_password: twoFactorPassword,
      })) as TwoFactorSetup;
      setTwoFactorSetup(setup);
      setTwoFactorCode("");
      setMessage("Scan the authenticator secret, then enter a current code to finish enabling two-step verification.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start two-step verification.");
    } finally {
      finish();
    }
  }

  async function enableTwoFactor() {
    begin("two-factor-enable");
    try {
      const status = (await apiPost("/api/settings/my/two-factor/enable", {
        code: twoFactorCode,
      })) as TwoFactorStatus;
      setTwoFactorStatus(status);
      setTwoFactorPassword("");
      setTwoFactorCode("");
      setMessage("Two-step verification enabled. Save the recovery codes somewhere secure.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not enable two-step verification.");
    } finally {
      finish();
    }
  }

  async function disableTwoFactor() {
    begin("two-factor-disable");
    try {
      const status = (await apiPost("/api/settings/my/two-factor/disable", {
        current_password: twoFactorPassword,
        code: twoFactorCode,
      })) as TwoFactorStatus;
      setTwoFactorStatus(status);
      setTwoFactorSetup(null);
      setTwoFactorPassword("");
      setTwoFactorCode("");
      setMessage("Two-step verification disabled.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disable two-step verification.");
    } finally {
      finish();
    }
  }

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading My Settings…</div>;
  }
  if (!user || !prefs) {
    return (
      <div className="p-6 text-sm text-red-700">
        {error || "My Settings unavailable."}
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">My Settings</h1>
        <p className="text-sm text-slate-500 mt-1">
          Personal settings apply only to your account and never change organization permissions.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {message}
        </div>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900 mb-4">Profile</h2>
        <div className="flex items-center gap-5 mb-5">
          <div className="w-20 h-20 rounded-full overflow-hidden bg-slate-100 border border-slate-200 flex items-center justify-center">
            {user.profile_photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={fileUrl(user.profile_photo_url)}
                alt="Profile"
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-2xl text-slate-400">
                {user.first_name.charAt(0).toUpperCase()}
              </span>
            )}
          </div>
          <div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={uploadPhoto}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={busy === "photo"}
              className="px-3 py-2 rounded-md bg-slate-900 text-white text-sm disabled:opacity-50"
            >
              {busy === "photo" ? "Uploading…" : "Change photo"}
            </button>
          </div>
        </div>

        <form onSubmit={saveProfile} className="grid gap-4 md:grid-cols-2">
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">First name</span>
            <input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Last name</span>
            <input
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Email</span>
            <input
              value={user.email}
              disabled
              className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-slate-50 text-slate-500"
            />
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Phone</span>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </label>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={busy === "profile"}
              className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium disabled:opacity-50"
            >
              {busy === "profile" ? "Saving…" : "Save profile"}
            </button>
          </div>
        </form>
      </section>

      <form onSubmit={savePreferences} className="rounded-lg border border-slate-200 bg-white p-5 space-y-4">
        <div>
          <h2 className="font-semibold text-slate-900">Notifications & email</h2>
          <p className="text-sm text-slate-500 mt-1">
            Event-specific notification rules will use these personal defaults as communication features are added.
          </p>
        </div>

        <label className="flex gap-3 items-start">
          <input
            type="checkbox"
            checked={prefs.email_notifications_enabled}
            onChange={(e) =>
              setPrefs({ ...prefs, email_notifications_enabled: e.target.checked })
            }
            className="mt-1"
          />
          <span>
            <span className="block text-sm font-medium text-slate-800">Email notifications</span>
            <span className="block text-xs text-slate-500">Allow email notifications for your account.</span>
          </span>
        </label>

        <label>
          <span className="block text-sm font-medium text-slate-800 mb-1">Reply-to email</span>
          <input
            type="email"
            value={prefs.reply_to_email || ""}
            onChange={(e) =>
              setPrefs({ ...prefs, reply_to_email: e.target.value || null })
            }
            placeholder={user.email}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
          />
        </label>

        <label>
          <span className="block text-sm font-medium text-slate-800 mb-1">Email signature</span>
          <textarea
            value={prefs.email_signature || ""}
            onChange={(e) =>
              setPrefs({ ...prefs, email_signature: e.target.value || null })
            }
            maxLength={2000}
            rows={5}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
          />
        </label>

        <div className="grid gap-4 md:grid-cols-2">
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Language override</span>
            <select
              value={prefs.language_override || ""}
              onChange={(e) =>
                setPrefs({ ...prefs, language_override: e.target.value || null })
              }
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
            >
              <option value="">Use organization default</option>
              <option value="en">English</option>
              <option value="es">Spanish</option>
            </select>
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Export format override</span>
            <select
              value={prefs.export_format_override || ""}
              onChange={(e) =>
                setPrefs({
                  ...prefs,
                  export_format_override:
                    (e.target.value as "CSV" | "EXCEL") || null,
                })
              }
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
            >
              <option value="">Use organization default</option>
              <option value="CSV">CSV</option>
              <option value="EXCEL">Excel</option>
            </select>
          </label>
        </div>

        <button
          type="submit"
          disabled={busy === "preferences"}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium disabled:opacity-50"
        >
          {busy === "preferences" ? "Saving…" : "Save personal preferences"}
        </button>
      </form>

      <form onSubmit={changePassword} className="rounded-lg border border-slate-200 bg-white p-5 space-y-4">
        <div>
          <h2 className="font-semibold text-slate-900">Password</h2>
          <p className="text-sm text-slate-500 mt-1">
            Changing your password uses the existing authenticated password-change flow.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Current password</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">New password</span>
            <input
              type="password"
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Confirm new password</span>
            <input
              type="password"
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={busy === "password"}
          className="px-4 py-2 rounded-md bg-slate-900 text-white text-sm font-medium disabled:opacity-50"
        >
          {busy === "password" ? "Updating…" : "Change password"}
        </button>
      </form>

      <section className="rounded-lg border border-slate-200 bg-white p-5 space-y-4">
        <div>
          <h2 className="font-semibold text-slate-900">Two-step verification</h2>
          <p className="text-sm text-slate-500 mt-1">
            Protect your login with any authenticator app using time-based verification codes.
          </p>
        </div>
        <div className="text-sm">
          Status: <strong>{twoFactorStatus?.enabled ? "Enabled" : "Not enabled"}</strong>
          {twoFactorStatus?.enabled ? ` · ${twoFactorStatus.recovery_codes_remaining} recovery codes remaining` : ""}
        </div>

        {twoFactorSetup && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-4 space-y-3">
            <div>
              <div className="text-sm font-medium text-amber-900">Authenticator secret</div>
              <code className="block mt-1 text-sm break-all">{twoFactorSetup.secret}</code>
            </div>
            <div>
              <div className="text-sm font-medium text-amber-900">Recovery codes — each works once</div>
              <div className="grid grid-cols-2 gap-1 mt-2 font-mono text-sm">
                {twoFactorSetup.recovery_codes.map((code) => <span key={code}>{code}</span>)}
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Current password</span>
            <input type="password" value={twoFactorPassword} onChange={(e) => setTwoFactorPassword(e.target.value)} className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" />
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Authenticator / recovery code</span>
            <input value={twoFactorCode} onChange={(e) => setTwoFactorCode(e.target.value)} className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono" placeholder="123456" />
          </label>
        </div>

        {!twoFactorStatus?.enabled ? (
          <div className="flex gap-3">
            {!twoFactorSetup ? (
              <button type="button" onClick={startTwoFactorSetup} disabled={!twoFactorPassword || busy === "two-factor-setup"} className="px-4 py-2 rounded-md bg-slate-900 text-white text-sm disabled:opacity-50">
                {busy === "two-factor-setup" ? "Starting…" : "Set up two-step verification"}
              </button>
            ) : (
              <button type="button" onClick={enableTwoFactor} disabled={!twoFactorCode || busy === "two-factor-enable"} className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm disabled:opacity-50">
                {busy === "two-factor-enable" ? "Verifying…" : "Verify and enable"}
              </button>
            )}
          </div>
        ) : (
          <button type="button" onClick={disableTwoFactor} disabled={!twoFactorPassword || !twoFactorCode || busy === "two-factor-disable"} className="px-4 py-2 rounded-md border border-red-300 text-red-700 text-sm disabled:opacity-50">
            {busy === "two-factor-disable" ? "Disabling…" : "Disable two-step verification"}
          </button>
        )}
        <p className="text-xs text-slate-500">Login history remains the next separate Phase 3.6 security batch.</p>
      </section>
    </div>
  );
}
