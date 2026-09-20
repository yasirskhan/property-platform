// ============================================================
// ModuleTabs.tsx
// ------------------------------------------------------------
// Two-row tab navigation used inside a module.
//
// Row 1 (topTabs):    Receivables | Payables | Bank Accounts | ...
// Row 2 (subTabs):    Bills | Payments | Recurring | Loans | ...
//
// Both rows are optional. If a page only needs one row,
// pass only topTabs.
//
// The active tab is determined by matching the current pathname.
// ============================================================

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// ------------------------------------------------------------
// Types
// ------------------------------------------------------------
export type Tab = {
  label: string;
  href: string;
};

type ModuleTabsProps = {
  topTabs?: Tab[];
  subTabs?: Tab[];
};

// ------------------------------------------------------------
// Component
// ------------------------------------------------------------
export default function ModuleTabs({ topTabs, subTabs }: ModuleTabsProps) {
  const pathname = usePathname();

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <div className="bg-white border-b border-slate-200">
      {/* Top row of tabs */}
      {topTabs && topTabs.length > 0 && (
        <div className="flex items-center gap-6 px-6 overflow-x-auto">
          {topTabs.map((tab) => {
            const active = isActive(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`py-3 text-sm whitespace-nowrap border-b-2 transition-colors ${
                  active
                    ? "border-blue-600 text-blue-700 font-medium"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      )}

      {/* Sub row of tabs */}
      {subTabs && subTabs.length > 0 && (
        <div className="flex items-center gap-5 px-6 border-t border-slate-100 overflow-x-auto">
          {subTabs.map((tab) => {
            const active = isActive(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`py-2 text-xs whitespace-nowrap border-b-2 transition-colors ${
                  active
                    ? "border-blue-600 text-blue-700 font-medium"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}