// ============================================================
// TopBar.tsx
// ------------------------------------------------------------
// The blue top bar, matching AppFolio's layout.
//
// Shows: logo | search | Add Functionality | Help & Training | user menu
//
// The user menu has: Profile, General Settings, Log out.
// Search is a placeholder for now — wires up later.
// ============================================================

"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Search,
  Plus,
  HelpCircle,
  ChevronDown,
  LogOut,
  User as UserIcon,
  Settings as SettingsIcon,
} from "lucide-react";
import { clearToken, fileUrl } from "@/lib/api";

// ------------------------------------------------------------
// Props
// ------------------------------------------------------------
type TopBarProps = {
  user: {
    id: number;
    first_name: string;
    last_name: string;
    role: string;
    profile_photo_url: string | null;
  };
};

// ------------------------------------------------------------
// Component
// ------------------------------------------------------------
export default function TopBar({ user }: TopBarProps) {
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  return (
    <header className="h-14 bg-[#1e5aa8] text-white flex items-center px-4 flex-shrink-0">
      {/* Left: search */}
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search AppFolio..."
            className="w-full bg-white text-slate-900 text-sm pl-9 pr-3 py-1.5 rounded border-0 focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
        </div>
      </div>

      {/* Right: actions */}
      <div className="ml-auto flex items-center gap-1">
        {/* Add Functionality */}
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-sm hover:bg-white/10 rounded">
          <Plus className="w-4 h-4" />
          <span className="hidden md:inline">Add Functionality</span>
          <ChevronDown className="w-3 h-3" />
        </button>

        {/* Help & Training */}
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-sm hover:bg-white/10 rounded">
          <HelpCircle className="w-4 h-4" />
          <span className="hidden md:inline">Help &amp; Training</span>
          <ChevronDown className="w-3 h-3" />
        </button>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 px-2 py-1.5 hover:bg-white/10 rounded"
          >
            {user.profile_photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={fileUrl(user.profile_photo_url)}
                alt={user.first_name}
                className="w-7 h-7 rounded-full object-cover border border-white/30"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-xs font-medium">
                {user.first_name.charAt(0).toUpperCase()}
              </div>
            )}
            <span className="hidden md:inline text-sm">
              {user.first_name} {user.last_name}
            </span>
            <ChevronDown className="w-3 h-3" />
          </button>

          {menuOpen && (
            <>
              {/* click-outside overlay */}
              <div
                className="fixed inset-0 z-10"
                onClick={() => setMenuOpen(false)}
              />
              {/* dropdown */}
              <div className="absolute right-0 top-full mt-1 w-52 bg-white text-slate-800 rounded shadow-lg border border-slate-200 z-20 py-1">
                <Link
                  href="/dashboard/profile"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50"
                >
                  <UserIcon className="w-4 h-4" />
                  My Profile
                </Link>
                <Link
                  href="/dashboard/settings/company"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50"
                >
                  <SettingsIcon className="w-4 h-4" />
                  General Settings
                </Link>
                <div className="border-t border-slate-100 my-1" />
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50 text-red-600"
                >
                  <LogOut className="w-4 h-4" />
                  Log out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}