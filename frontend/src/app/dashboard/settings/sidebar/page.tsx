// ============================================================
// Sidebar Customization — DEPRECATED
// ------------------------------------------------------------
// Route: /dashboard/settings/sidebar
//
// Superseded by /dashboard/settings/permissions (the "My
// Preferences" tab). This page redirects there so old links and
// bookmarks keep working.
// ============================================================

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SidebarSettingsRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard/settings/permissions?tab=preferences");
  }, [router]);

  return (
    <div className="p-8 text-slate-500">Redirecting to Permissions…</div>
  );
}