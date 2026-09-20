// ============================================================
// RightPanel.tsx
// ------------------------------------------------------------
// The contextual right-side panel that appears on every page.
//
// Sections: TASKS / REPORTS / HELP TOPICS
//
// Each page decides what to pass in. Pages that don't pass
// anything simply don't render the panel (opt-in).
//
// Panel width: 280px. Collapsible via the header chevron.
// ============================================================

"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronUp, Star, Info, ListChecks } from "lucide-react";

// ------------------------------------------------------------
// Types
// ------------------------------------------------------------
export type RightPanelTask = {
  label: string;
  href?: string;         // if set, renders as a link
  badge?: string;        // optional badge (e.g. "NEW")
  onClick?: () => void;  // if set, renders as a button
};

export type RightPanelReport = {
  label: string;
  href: string;
};

export type RightPanelHelp = {
  label: string;
  href?: string;
};

export type RightPanelContent = {
  tasks?: RightPanelTask[];
  reports?: RightPanelReport[];
  help?: RightPanelHelp[];
};

// ------------------------------------------------------------
// Props
// ------------------------------------------------------------
type RightPanelProps = {
  content: RightPanelContent;
};

// ------------------------------------------------------------
// Component
// ------------------------------------------------------------
export default function RightPanel({ content }: RightPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  const hasAnything =
    (content.tasks && content.tasks.length > 0) ||
    (content.reports && content.reports.length > 0) ||
    (content.help && content.help.length > 0);

  if (!hasAnything) return null;

  return (
    <aside
      className={`${
        collapsed ? "w-12" : "w-[280px]"
      } bg-slate-50 border-l border-slate-200 flex-shrink-0 transition-all duration-150`}
    >
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        {!collapsed && (
          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
            Tools
          </span>
        )}
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="p-1 rounded hover:bg-slate-200"
          title={collapsed ? "Expand panel" : "Collapse panel"}
        >
          <ChevronUp
            className={`w-4 h-4 text-slate-500 transition-transform ${
              collapsed ? "rotate-90" : ""
            }`}
          />
        </button>
      </div>

      {!collapsed && (
        <div className="p-4 space-y-6 overflow-y-auto">
          {/* TASKS */}
          {content.tasks && content.tasks.length > 0 && (
            <section>
              <h3 className="flex items-center gap-2 text-xs font-semibold text-blue-700 uppercase tracking-wide mb-2">
                <Star className="w-3 h-3" />
                Tasks
              </h3>
              <ul className="space-y-1.5">
                {content.tasks.map((task, i) => (
                  <li key={i}>
                    {task.href ? (
                      <Link
                        href={task.href}
                        className="flex items-center gap-1.5 text-sm text-blue-700 hover:underline"
                      >
                        <span>{task.label}</span>
                        {task.badge && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                            {task.badge}
                          </span>
                        )}
                      </Link>
                    ) : (
                      <button
                        onClick={task.onClick}
                        className="flex items-center gap-1.5 text-sm text-blue-700 hover:underline text-left"
                      >
                        <span>{task.label}</span>
                        {task.badge && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                            {task.badge}
                          </span>
                        )}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* REPORTS */}
          {content.reports && content.reports.length > 0 && (
            <section>
              <h3 className="flex items-center gap-2 text-xs font-semibold text-blue-700 uppercase tracking-wide mb-2">
                <ListChecks className="w-3 h-3" />
                Reports
              </h3>
              <ul className="space-y-1.5">
                {content.reports.map((report, i) => (
                  <li key={i}>
                    <Link
                      href={report.href}
                      className="text-sm text-blue-700 hover:underline"
                    >
                      {report.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* HELP TOPICS */}
          {content.help && content.help.length > 0 && (
            <section>
              <h3 className="flex items-center gap-2 text-xs font-semibold text-blue-700 uppercase tracking-wide mb-2">
                <Info className="w-3 h-3" />
                Help Topics
              </h3>
              <ul className="space-y-1.5">
                {content.help.map((h, i) => (
                  <li key={i}>
                    {h.href ? (
                      <Link
                        href={h.href}
                        className="text-sm text-blue-700 hover:underline"
                      >
                        {h.label}
                      </Link>
                    ) : (
                      <span className="text-sm text-blue-700">{h.label}</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </aside>
  );
}