// ============================================================
// Owner → Settings → Email
// ------------------------------------------------------------
// Owners configure their organization's custom SMTP server.
// All input is stored encrypted in the backend.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiFetch } from "@/lib/api";

type Settings = {
  id: number;
  organization_id: number;
  from_email: string;
  from_name: string;
  reply_to_email: string | null;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_use_tls: boolean;
  is_enabled: boolean;
  last_test_at: string | null;
  verified_at: string | null;
  last_error: string | null;
};

export default function EmailSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [orgId, setOrgId] = useState<number | null>(null);
  const [hasExisting, setHasExisting] = useState(false);

  // Form fields
  const [fromEmail, setFromEmail] = useState("");
  const [fromName, setFromName] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpUseTls, setSmtpUseTls] = useState(true);
  const [isEnabled, setIsEnabled] = useState(true);
  const [testTo, setTestTo] = useState("");

  // Load current user + settings
  useEffect(() => {
    (async () => {
      try {
        const me = await apiGet("/auth/me");
        if (me.role !== "owner" && me.role !== "admin") {
          setError("Only owners can access this page.");
          setLoading(false);
          return;
        }
        if (!me.organization_id) {
          setError("Your account isn't linked to an organization.");
          setLoading(false);
          return;
        }
        setOrgId(me.organization_id);

        try {
          const s: Settings = await apiGet(
            `/organizations/${me.organization_id}/email-settings`
          );
          setFromEmail(s.from_email);
          setFromName(s.from_name);
          setReplyTo(s.reply_to_email || "");
          setSmtpHost(s.smtp_host);
          setSmtpPort(s.smtp_port);
          setSmtpUser(s.smtp_user);
          setSmtpUseTls(s.smtp_use_tls);
          setIsEnabled(s.is_enabled);
          setHasExisting(true);
        } catch {
          // No settings yet — start with blank form
          setHasExisting(false);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      if (!orgId) throw new Error("Missing organization");

      const body: Record<string, unknown> = {
        from_email: fromEmail,
        from_name: fromName,
        reply_to_email: replyTo || null,
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_user: smtpUser,
        smtp_use_tls: smtpUseTls,
        is_enabled: isEnabled,
      };

      if (smtpPassword) body.smtp_password = smtpPassword;

      // If this is a first-time save, password is required
      if (!hasExisting && !smtpPassword) {
        throw new Error("Password is required for first-time setup");
      }

      const res = await apiFetch(`/organizations/${orgId}/email-settings`, {
        method: "PUT",
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Save failed");
      }

      setSuccess("Settings saved.");
      setSmtpPassword("");
      setHasExisting(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setTesting(true);
    try {
      if (!orgId) throw new Error("Missing organization");
      const result = await apiPost(
        `/organizations/${orgId}/email-settings/test`,
        { to: testTo }
      );
      setSuccess(result.detail || "Test sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return <div className="text-slate-500">Loading…</div>;
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Email Settings</h1>
        <p className="text-slate-500 mt-1">
          Configure your organization&apos;s email server so tenants and crew see emails from you.
        </p>
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

      <form onSubmit={handleSave} className="space-y-6 bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-semibold text-slate-900">Sender Identity</h2>

        <Field label="From Name">
          <input
            type="text"
            value={fromName}
            onChange={(e) => setFromName(e.target.value)}
            placeholder="Smith Property Management"
            className="input"
          />
        </Field>

        <Field label="From Email">
          <input
            type="email"
            required
            value={fromEmail}
            onChange={(e) => setFromEmail(e.target.value)}
            placeholder="noreply@yourdomain.com"
            className="input"
          />
        </Field>

        <Field label="Reply-To Email (optional)">
          <input
            type="email"
            value={replyTo}
            onChange={(e) => setReplyTo(e.target.value)}
            placeholder="support@yourdomain.com"
            className="input"
          />
        </Field>

        <hr className="border-slate-100" />

        <h2 className="font-semibold text-slate-900">SMTP Server</h2>

        <Field label="SMTP Host">
          <input
            type="text"
            required
            value={smtpHost}
            onChange={(e) => setSmtpHost(e.target.value)}
            placeholder="smtp.gmail.com"
            className="input"
          />
          <p className="text-xs text-slate-500 mt-1">
            Gmail: <code>smtp.gmail.com</code> · Outlook: <code>smtp-mail.outlook.com</code> · Custom: your hosting provider
          </p>
        </Field>

        <Field label="SMTP Port">
          <input
            type="number"
            required
            value={smtpPort}
            onChange={(e) => setSmtpPort(parseInt(e.target.value))}
            className="input"
          />
          <p className="text-xs text-slate-500 mt-1">
            587 (TLS) or 465 (SSL)
          </p>
        </Field>

        <Field label="SMTP Username">
          <input
            type="text"
            required
            value={smtpUser}
            onChange={(e) => setSmtpUser(e.target.value)}
            placeholder="you@yourdomain.com"
            className="input"
          />
        </Field>

        <Field label="SMTP Password">
          <input
            type="password"
            value={smtpPassword}
            onChange={(e) => setSmtpPassword(e.target.value)}
            placeholder={hasExisting ? "(unchanged — leave blank)" : "App password"}
            className="input"
          />
          <p className="text-xs text-slate-500 mt-1">
            For Gmail, use an App Password, not your login password.
          </p>
        </Field>

        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="useTls"
            checked={smtpUseTls}
            onChange={(e) => setSmtpUseTls(e.target.checked)}
            className="w-4 h-4"
          />
          <label htmlFor="useTls" className="text-sm text-slate-700">
            Use TLS (recommended)
          </label>
        </div>

        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="isEnabled"
            checked={isEnabled}
            onChange={(e) => setIsEnabled(e.target.checked)}
            className="w-4 h-4"
          />
          <label htmlFor="isEnabled" className="text-sm text-slate-700">
            Enable custom email (otherwise platform default is used)
          </label>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="bg-slate-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Settings"}
        </button>
      </form>

      {hasExisting && (
        <form onSubmit={handleTest} className="space-y-4 bg-white rounded-xl border border-slate-200 p-6 mt-6">
          <h2 className="font-semibold text-slate-900">Send a Test Email</h2>
          <Field label="Send test email to">
            <input
              type="email"
              required
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              placeholder="you@yourdomain.com"
              className="input"
            />
          </Field>
          <button
            type="submit"
            disabled={testing}
            className="bg-white text-slate-900 border border-slate-300 px-6 py-2.5 rounded-lg font-medium hover:bg-slate-50 disabled:opacity-50"
          >
            {testing ? "Sending…" : "Send Test Email"}
          </button>
        </form>
      )}
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