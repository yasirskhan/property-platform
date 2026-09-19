// ============================================================
// /dashboard — Redirects to the correct role dashboard.
// ------------------------------------------------------------
// If a user lands on /dashboard directly, send them to
// /dashboard/{their-role}.
// ============================================================

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiGet, isLoggedIn, clearToken } from "@/lib/api";

export default function DashboardRedirect() {
  const router = useRouter();

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }

    apiGet("/auth/me")
      .then((me) => {
        const roleRoutes: Record<string, string> = {
          admin: "/dashboard/admin",
          owner: "/dashboard/owner",
          manager: "/dashboard/manager",
          crew: "/dashboard/crew",
          tenant: "/dashboard/tenant",
        };
        const target = roleRoutes[me.role] || "/login";
        router.replace(target);
      })
      .catch(() => {
        clearToken();
        router.replace("/login");
      });
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center text-slate-500">
      Redirecting…
    </div>
  );
}