// ============================================================
// Dashboard Layout
// ------------------------------------------------------------
// Three-zone shell that wraps every dashboard page.
//
//   +---------+------------------------+---------+
//   | Sidebar |  TopBar                |  Right  |
//   |         +------------------------+  Panel  |
//   |         |  Page content          |         |
//   +---------+------------------------+---------+
//
// Right panel is hidden by default - pages opt in later.
//
// Providers mounted here (outer -> inner):
//   1. CurrencyProvider  - loads /api/settings/display, sets
//                          currency + date format in lib/money.ts
//   2. DisplayProvider   - applies theme/density/font/accent
//                          to <html> attributes
//   3. MenuProvider      - loads the resolved menu
//
// See PROJECT_MASTER.md Sections 58 and 59.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, clearToken, isLoggedIn } from "@/lib/api";
import Sidebar from "@/components/shell/Sidebar";
import TopBar from "@/components/shell/TopBar";
import { MenuProvider } from "@/contexts/MenuContext";
import { CurrencyProvider } from "@/contexts/CurrencyContext";
import { DisplayProvider } from "@/contexts/DisplayContext";

type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  profile_photo_url: string | null;
  organization_id: number | null;
};

type OrgInfo = {
  id: number;
  name: string;
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [orgName, setOrgName] = useState<string>("");

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }

    apiGet("/auth/me")
      .then(async (u: User) => {
        const role = String(u.role || "").toUpperCase();
        if (
          u.organization_id &&
          (role === "ADMIN" || role === "OWNER")
        ) {
          try {
            const billing = await apiGet("/api/billing/state");
            if (billing.organization_state === "PENDING_BILLING") {
              router.replace("/signup?checkout=pending");
              return;
            }
          } catch {
            router.replace("/signup?checkout=pending");
            return;
          }
        }

        setUser(u);

        if (u.organization_id) {
          try {
            const org: OrgInfo = await apiGet(
              `/organizations/${u.organization_id}`
            );
            setOrgName(org.name);
          } catch {
            setOrgName("My Organization");
          }
        } else {
          setOrgName("My Organization");
        }
      })
      .catch(() => {
        clearToken();
        router.push("/login");
      });
  }, [router]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        Loading...
      </div>
    );
  }

  return (
    <CurrencyProvider>
      <DisplayProvider>
        <MenuProvider>
          <div className="min-h-screen flex bg-slate-50">
            {/* LEFT: sidebar */}
            <Sidebar orgName={orgName} />

            {/* RIGHT OF SIDEBAR: topbar + content */}
            <div className="flex-1 flex flex-col min-w-0">
              <TopBar user={user} />
              <main className="flex-1 overflow-auto">
                <div className="p-6">{children}</div>
              </main>
            </div>
          </div>
        </MenuProvider>
      </DisplayProvider>
    </CurrencyProvider>
  );
}