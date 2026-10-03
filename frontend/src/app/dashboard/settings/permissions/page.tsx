// ============================================================
// Permissions Settings Page
// ------------------------------------------------------------
// Route: /dashboard/settings/permissions
//
// Three tabs:
//   Roles            — role-by-menu matrix (Admin/Owner/Manager)
//   Users            — per-user overrides        (Admin/Owner/Manager)
//   My Preferences   — personal order + hides    (everyone)
//
// The tabs a user can see are decided here (and enforced again
// on the backend — never trust the client).
//
// A save in Roles or Users triggers a refresh of MenuContext so
// the sidebar updates without a page reload.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { apiGet } from "@/lib/api";
import { useMenu } from "@/contexts/MenuContext";
import { useDisplay } from "@/contexts/DisplayContext";
import Flag from "@/components/features/Flag";
import RoleMatrix from "@/components/permissions/RoleMatrix";
import UserOverrides from "@/components/permissions/UserOverrides";
import MyPreferences from "@/components/permissions/MyPreferences";

type User = {
  id: number;
  role: string;
};

type TabKey = "roles" | "users" | "preferences";

const ROLE_CAN_EDIT_ROLES = ["ADMIN", "OWNER", "MANAGER"];
const ROLE_CAN_EDIT_USERS = ["ADMIN", "OWNER", "MANAGER"];

export default function PermissionsPage() {
  const router = useRouter();
  const { refresh } = useMenu();
  const { prefs } = useDisplay();

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("preferences");

  useEffect(() => {
    apiGet("/auth/me")
      .then((u: User) => {
        setUser(u);
        const requestedTab = new URLSearchParams(window.location.search).get("tab");
        const normalizedRole = String(u.role).toUpperCase();
        const canEditRoles = ROLE_CAN_EDIT_ROLES.includes(normalizedRole);
        const canEditUsers = ROLE_CAN_EDIT_USERS.includes(normalizedRole);

        if (requestedTab === "preferences") {
          setTab("preferences");
        } else if (requestedTab === "users" && canEditUsers) {
          setTab("users");
        } else if (requestedTab === "roles" && canEditRoles) {
          setTab("roles");
        } else if (canEditRoles) {
          setTab("roles");
        } else {
          setTab("preferences");
        }
        setLoading(false);
      })
      .catch(() => {
        router.push("/login");
      });
  }, [router]);

  if (loading || !user) {
    return <div className="p-8 text-slate-500">Loading…</div>;
  }

  const normalizedRole = String(user.role || "").toUpperCase();
  const showRoles = ROLE_CAN_EDIT_ROLES.includes(normalizedRole);
  const showUsers = ROLE_CAN_EDIT_USERS.includes(normalizedRole);

  const tabs: { key: TabKey; label: string }[] = [];
  if (showRoles) tabs.push({ key: "roles", label: "Roles" });
  if (showUsers) tabs.push({ key: "users", label: "Users" });
  tabs.push({ key: "preferences", label: "My Preferences" });

  return (
    <div
      className="max-w-5xl"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <Link
        href="/dashboard/settings"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to settings
      </Link>

      <div className="flex items-start justify-between gap-4 mb-1">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-6 h-6 text-slate-700" />
          <h1 className="text-2xl font-semibold text-slate-900">
            Permissions
          </h1>
        </div>
        <Flag name="release.accounting.gl_account_permissions">
          <button
            type="button"
            disabled
            className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60"
          >
            GL Account Permissions
          </button>
        </Flag>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Control what each role sees, override for specific users, and
        personalize your own sidebar.
      </p>

      {/* Tabs */}
      <div className="border-b border-slate-200 mb-6">
        <div className="flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm border-b-2 -mb-px transition-colors ${
                tab === t.key
                  ? "border-blue-600 text-blue-600 font-medium"
                  : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "roles" && showRoles && (
        <RoleMatrix onSaved={() => refresh()} />
      )}
      {tab === "users" && showUsers && (
        <UserOverrides onSaved={() => refresh()} />
      )}
      {tab === "preferences" && <MyPreferences onSaved={() => refresh()} />}
    </div>
  );
}