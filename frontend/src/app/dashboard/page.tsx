// ============================================================
// Dashboard Home
// ------------------------------------------------------------
// The landing page at /dashboard. Same for every role.
//
// Visibility of what you can do next is driven by the sidebar
// (menu permissions) — not by a hardcoded role redirect.
//
// This is intentionally minimal for now. We'll build a proper
// role-aware dashboard later.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
};

export default function DashboardHome() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    apiGet("/auth/me").then(setUser).catch(() => setUser(null));
  }, []);

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold text-slate-900 mb-1">
        {user ? `Welcome, ${user.first_name}` : "Welcome"}
      </h1>
      <p className="text-sm text-slate-500 mb-8">
        Pick a module from the sidebar to get started.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-5 bg-white border border-slate-200 rounded-lg">
          <div className="text-sm text-slate-500">Signed in as</div>
          <div className="text-slate-900 font-medium mt-1">
            {user ? `${user.first_name} ${user.last_name}` : "…"}
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            {user?.email || ""}
          </div>
        </div>

        <div className="p-5 bg-white border border-slate-200 rounded-lg">
          <div className="text-sm text-slate-500">Role</div>
          <div className="text-slate-900 font-medium mt-1">
            {user?.role || "…"}
          </div>
        </div>
      </div>
    </div>
  );
}