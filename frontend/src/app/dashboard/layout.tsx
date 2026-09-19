// ============================================================
// Dashboard Layout
// ------------------------------------------------------------
// Wraps every dashboard page with a shared top nav bar.
// Shows the user's avatar, name, and a Log Out button.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, clearToken, isLoggedIn, fileUrl } from "@/lib/api";

type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  profile_photo_url: string | null;
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }
    apiGet("/auth/me")
      .then(setUser)
      .catch(() => {
        clearToken();
        router.push("/login");
      });
  }, [router]);

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="font-bold text-slate-900">
              Property Platform
            </Link>
            <span className="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded-full uppercase tracking-wide">
              {user.role}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard/profile"
              className="flex items-center gap-3 hover:opacity-80"
            >
              {user.profile_photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={fileUrl(user.profile_photo_url)}
                  alt={user.first_name}
                  className="w-8 h-8 rounded-full object-cover border border-slate-200"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-sm font-medium">
                  {user.first_name.charAt(0).toUpperCase()}
                </div>
              )}
              <span className="text-sm text-slate-600">
                {user.first_name} {user.last_name}
              </span>
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm text-slate-500 hover:text-slate-900"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}