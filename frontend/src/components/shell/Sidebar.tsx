// ============================================================
// Sidebar.tsx
// ------------------------------------------------------------
// The dark left sidebar.
//
// Reads the RESOLVED menu from MenuContext, which itself loads
// from the backend (GET /api/menu/me). This component does NOT
// decide visibility — it only renders what the backend returned.
//
// Display info (label, href, icon) comes from lib/menuConfig.ts.
// If the backend sends a key we don't know how to render, we
// skip it silently. That way, adding a new backend menu key
// without updating the frontend never breaks the sidebar.
// ============================================================

"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Calendar,
  Building2,
  HomeIcon,
  Users,
  DollarSign,
  Wrench,
  BarChart3,
  MessageSquare,
  Sparkles,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { getMenuEntry, MenuEntry } from "@/lib/menuConfig";
import { useMenu } from "@/contexts/MenuContext";

// ------------------------------------------------------------
// Icon key -> lucide component
// ------------------------------------------------------------
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  home: Home,
  calendar: Calendar,
  building: Building2,
  "home-building": HomeIcon,
  users: Users,
  "dollar-sign": DollarSign,
  wrench: Wrench,
  "bar-chart": BarChart3,
  "message-square": MessageSquare,
  sparkles: Sparkles,
};

// ------------------------------------------------------------
// A resolved top-level item, with its resolved children
// ------------------------------------------------------------
type TopLevel = {
  entry: MenuEntry;
  children: MenuEntry[];
};

// ------------------------------------------------------------
// Props
// ------------------------------------------------------------
type SidebarProps = {
  orgName: string;
};

// ------------------------------------------------------------
// Component
// ------------------------------------------------------------
export default function Sidebar({ orgName }: SidebarProps) {
  const pathname = usePathname();
  const { items, loading } = useMenu();

  // ----------------------------------------------------------
  // Build top-level + children from the flat resolved list.
  // The backend returns items already in the correct order;
  // we just group children under their parent.
  // ----------------------------------------------------------
  const topLevel: TopLevel[] = [];
  const indexByKey = new Map<string, number>();

  for (const it of items) {
    const entry = getMenuEntry(it.key);
    if (!entry) continue; // backend key we don't know how to render

    if (it.parent === null) {
      indexByKey.set(it.key, topLevel.length);
      topLevel.push({ entry, children: [] });
    } else {
      const parentIdx = indexByKey.get(it.parent);
      if (parentIdx === undefined) continue; // orphan child, skip
      topLevel[parentIdx].children.push(entry);
    }
  }

  // ----------------------------------------------------------
  // Which expandable items are open?
  // Default: any parent that contains the current path.
  // ----------------------------------------------------------
  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    const opened = new Set<string>();
    for (const group of topLevel) {
      if (group.children.length === 0) continue;
      const isActive = group.children.some((sub) =>
        pathname.startsWith(sub.href)
      );
      if (isActive) opened.add(group.entry.key);
    }
    setOpenKeys(opened);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, items]);

  function toggle(key: string) {
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // ----------------------------------------------------------
  // Render
  // ----------------------------------------------------------
  return (
    <aside className="w-[220px] min-h-screen bg-[#1e2a3a] text-white flex flex-col flex-shrink-0">
      {/* Top: logo / app name */}
      <div className="px-5 py-4 border-b border-white/10">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center text-xs font-bold">
            PM
          </div>
          <span className="text-sm font-semibold">Property Manager</span>
        </div>
      </div>

      {/* Middle: nav items */}
      <nav className="flex-1 overflow-y-auto py-2">
        {loading && items.length === 0 && (
          <div className="px-5 py-3 text-xs text-slate-500">
            Loading menu…
          </div>
        )}

        {!loading && topLevel.length === 0 && (
          <div className="px-5 py-3 text-xs text-slate-500">
            No menu items available.
          </div>
        )}

        {topLevel.map(({ entry, children }) => {
          const Icon = ICON_MAP[entry.icon] || Home;
          const hasChildren = children.length > 0;
          const isOpen = openKeys.has(entry.key);
          const isActive =
            pathname === entry.href ||
            children.some((c) => pathname.startsWith(c.href));

          return (
            <div key={entry.key}>
              {/* Parent row */}
              <button
                onClick={() => (hasChildren ? toggle(entry.key) : undefined)}
                className={`w-full flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1 text-left">{entry.label}</span>
                {entry.badge && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-red-500 rounded-full">
                    {entry.badge}
                  </span>
                )}
                {hasChildren &&
                  (isOpen ? (
                    <ChevronDown className="w-3 h-3 flex-shrink-0" />
                  ) : (
                    <ChevronRight className="w-3 h-3 flex-shrink-0" />
                  ))}
              </button>

              {/* Sub-items (when open) */}
              {hasChildren && isOpen && (
                <div className="bg-black/20">
                  {children.map((sub) => {
                    const subActive = pathname === sub.href;
                    return (
                      <Link
                        key={sub.key}
                        href={sub.href}
                        className={`block pl-12 pr-5 py-2 text-xs transition-colors ${
                          subActive
                            ? "bg-blue-600/40 text-white"
                            : "text-slate-400 hover:bg-white/5 hover:text-white"
                        }`}
                      >
                        {sub.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Bottom: org name */}
      <div className="px-5 py-4 border-t border-white/10">
        <div className="text-xs text-slate-400">Logged in as</div>
        <div className="text-sm text-white truncate">{orgName}</div>
      </div>
    </aside>
  );
}