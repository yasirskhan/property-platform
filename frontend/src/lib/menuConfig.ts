// ============================================================
// menuConfig.ts
// ------------------------------------------------------------
// Display layer for the menu system.
//
// The BACKEND is the source of truth for visibility, order, and
// hiding. This file only knows how to render each menu key:
// its label, its route, and its icon.
//
// Keys MUST match exactly what the backend returns from
// /api/menu/me. They are UPPERCASE, and children use
// PARENT.CHILD. If you add a key here, add it to the backend
// constants file too (app/constants/menu_keys.py).
// ============================================================

export type MenuEntry = {
  key: string;              // e.g. "ACCOUNTING.RECEIVABLES"
  label: string;            // e.g. "Receipts"
  href: string;             // e.g. "/dashboard/accounting/receipts"
  icon: string;             // icon key; Sidebar maps to a lucide component
  badge?: string;           // optional badge (e.g. "22")
};

// ------------------------------------------------------------
// Every menu key -> display info
// ------------------------------------------------------------
export const MENU_ENTRIES: Record<string, MenuEntry> = {
  // ---------- top-level ----------
  DASHBOARD:    { key: "DASHBOARD",    label: "Dashboard",     href: "/dashboard",                     icon: "home" },
  CALENDAR:     { key: "CALENDAR",     label: "Calendar",      href: "/dashboard/calendar",            icon: "calendar" },
  LEASING:      { key: "LEASING",      label: "Leasing",       href: "/dashboard/leasing",             icon: "building" },
  PROPERTIES:   { key: "PROPERTIES",   label: "Properties",    href: "/dashboard/properties",          icon: "home-building" },
  PEOPLE:       { key: "PEOPLE",       label: "People",        href: "/dashboard/team",                icon: "users" },
  ACCOUNTING:   { key: "ACCOUNTING",   label: "Accounting",    href: "/dashboard/accounting",          icon: "dollar-sign" },
  MAINTENANCE:  { key: "MAINTENANCE",  label: "Maintenance",   href: "/dashboard/maintenance",         icon: "wrench" },
  REPORTING:    { key: "REPORTING",    label: "Reporting",     href: "/dashboard/reporting",           icon: "bar-chart" },
  COMMUNICATION:{ key: "COMMUNICATION",label: "Communication", href: "/dashboard/communication",       icon: "message-square" },
  WHATS_NEW:    { key: "WHATS_NEW",    label: "What's New",    href: "/dashboard/whats-new",           icon: "sparkles", badge: "22" },

  // ---------- leasing children ----------
  "LEASING.LISTINGS":     { key: "LEASING.LISTINGS",     label: "Listings",         href: "/dashboard/leasing/listings",     icon: "" },
  "LEASING.APPLICATIONS": { key: "LEASING.APPLICATIONS", label: "Applications",     href: "/dashboard/leasing/applications", icon: "" },
  "LEASING.CRM":          { key: "LEASING.CRM",          label: "CRM",              href: "/dashboard/leasing/crm",          icon: "" },
  "LEASING.TEMPLATES":    { key: "LEASING.TEMPLATES",    label: "Lease Templates",  href: "/dashboard/leasing/templates",    icon: "" },

  // ---------- properties children ----------
  "PROPERTIES.ALL":       { key: "PROPERTIES.ALL",       label: "All Properties",   href: "/dashboard/properties",        icon: "" },
  "PROPERTIES.ADD":       { key: "PROPERTIES.ADD",       label: "Add Property",     href: "/dashboard/properties/new",    icon: "" },
  "PROPERTIES.UNITS":     { key: "PROPERTIES.UNITS",     label: "Units",            href: "/dashboard/units",             icon: "" },
  "PROPERTIES.GROUPS":    { key: "PROPERTIES.GROUPS",    label: "Property Groups",  href: "/dashboard/property-groups",   icon: "" },

  // ---------- people children ----------
  "PEOPLE.TEAM":          { key: "PEOPLE.TEAM",          label: "Team",             href: "/dashboard/team",       icon: "" },
  "PEOPLE.TENANTS":       { key: "PEOPLE.TENANTS",       label: "Tenants",          href: "/dashboard/tenants",    icon: "" },
  "PEOPLE.OWNERS":        { key: "PEOPLE.OWNERS",        label: "Owners",           href: "/dashboard/owners",     icon: "" },
  "PEOPLE.VENDORS":       { key: "PEOPLE.VENDORS",       label: "Vendors",          href: "/dashboard/vendors",    icon: "" },
  "PEOPLE.CONTACTS":      { key: "PEOPLE.CONTACTS",      label: "Contacts",         href: "/dashboard/contacts",   icon: "" },

  // ---------- accounting children ----------
  "ACCOUNTING.RECEIVABLES":     { key: "ACCOUNTING.RECEIVABLES",     label: "Receipts",          href: "/dashboard/accounting/receipts",        icon: "" },
  "ACCOUNTING.PAYABLES":        { key: "ACCOUNTING.PAYABLES",        label: "Bills",             href: "/dashboard/accounting/bills",           icon: "" },
  "ACCOUNTING.BANK_ACCOUNTS":   { key: "ACCOUNTING.BANK_ACCOUNTS",   label: "Bank Accounts",     href: "/dashboard/accounting/bank-accounts",   icon: "" },
  "ACCOUNTING.JOURNAL_ENTRIES": { key: "ACCOUNTING.JOURNAL_ENTRIES", label: "Journal Entries",   href: "/dashboard/accounting/journal-entries", icon: "" },
  "ACCOUNTING.BANK_TRANSFERS":  { key: "ACCOUNTING.BANK_TRANSFERS",  label: "Bank Transfers",    href: "/dashboard/accounting/transfers",       icon: "" },
  "ACCOUNTING.GL_ACCOUNTS":     { key: "ACCOUNTING.GL_ACCOUNTS",     label: "GL Accounts",       href: "/dashboard/accounting/gl-accounts",     icon: "" },
  "ACCOUNTING.DIAGNOSTICS":     { key: "ACCOUNTING.DIAGNOSTICS",     label: "Diagnostics",       href: "/dashboard/accounting/diagnostics",     icon: "" },
  "ACCOUNTING.ONLINE_PAYMENTS": { key: "ACCOUNTING.ONLINE_PAYMENTS", label: "Online Payments",   href: "/dashboard/accounting/online-payments", icon: "" },
  "ACCOUNTING.DEPOSITS":        { key: "ACCOUNTING.DEPOSITS",        label: "Bank Deposits",     href: "/dashboard/accounting/deposits",        icon: "" },
  "ACCOUNTING.MANAGEMENT_FEES": { key: "ACCOUNTING.MANAGEMENT_FEES", label: "Management Fees",   href: "/dashboard/accounting/management-fees", icon: "" },
  "ACCOUNTING.OWNER_STATEMENTS": { key: "ACCOUNTING.OWNER_STATEMENTS", label: "Owner Statements", href: "/dashboard/accounting/owner-statements", icon: "" },

  // ---------- maintenance children ----------
  "MAINTENANCE.WORK_ORDERS":     { key: "MAINTENANCE.WORK_ORDERS",     label: "Work Orders",           href: "/dashboard/maintenance/work-orders",     icon: "" },
  "MAINTENANCE.RECURRING":       { key: "MAINTENANCE.RECURRING",       label: "Recurring Work Orders", href: "/dashboard/maintenance/recurring",       icon: "" },
  "MAINTENANCE.INSPECTIONS":     { key: "MAINTENANCE.INSPECTIONS",     label: "Inspections",           href: "/dashboard/maintenance/inspections",     icon: "" },
  "MAINTENANCE.UNIT_TURNS":      { key: "MAINTENANCE.UNIT_TURNS",      label: "Unit Turns",            href: "/dashboard/maintenance/unit-turns",      icon: "" },
  "MAINTENANCE.PROJECTS":        { key: "MAINTENANCE.PROJECTS",        label: "Projects",              href: "/dashboard/maintenance/projects",        icon: "" },
  "MAINTENANCE.PURCHASE_ORDERS": { key: "MAINTENANCE.PURCHASE_ORDERS", label: "Purchase Orders",       href: "/dashboard/maintenance/purchase-orders", icon: "" },
  "MAINTENANCE.INVENTORY":       { key: "MAINTENANCE.INVENTORY",       label: "Inventory",             href: "/dashboard/maintenance/inventory",       icon: "" },
  "MAINTENANCE.FIXED_ASSETS":    { key: "MAINTENANCE.FIXED_ASSETS",    label: "Fixed Assets",          href: "/dashboard/maintenance/fixed-assets",    icon: "" },
  "MAINTENANCE.SMART":           { key: "MAINTENANCE.SMART",           label: "Smart Maintenance",     href: "/dashboard/maintenance/smart",           icon: "" },

  // ---------- reporting children ----------
  "REPORTING.ALL":     { key: "REPORTING.ALL",     label: "All Reports",       href: "/dashboard/reporting",          icon: "" },
  "REPORTING.BUILDER": { key: "REPORTING.BUILDER", label: "Custom Reports",    href: "/dashboard/reporting/builder",  icon: "" },

  // ---------- communication children ----------
  "COMMUNICATION.INBOX":     { key: "COMMUNICATION.INBOX",     label: "Inbox",     href: "/dashboard/communication/inbox",     icon: "" },
  "COMMUNICATION.MESSAGES":  { key: "COMMUNICATION.MESSAGES",  label: "Messages",  href: "/dashboard/communication/messages",  icon: "" },
  "COMMUNICATION.TEMPLATES": { key: "COMMUNICATION.TEMPLATES", label: "Templates", href: "/dashboard/communication/templates", icon: "" },
  "COMMUNICATION.SURVEYS":   { key: "COMMUNICATION.SURVEYS",   label: "Surveys",   href: "/dashboard/communication/surveys",   icon: "" },
};

// ------------------------------------------------------------
// Lookup helper. Returns undefined if the backend sends a key
// we don't know about yet — the Sidebar will skip it silently.
// ------------------------------------------------------------
export function getMenuEntry(key: string): MenuEntry | undefined {
  return MENU_ENTRIES[key];
}

// ------------------------------------------------------------
// Human-readable labels for roles (used in the Role Matrix UI)
// ------------------------------------------------------------
export const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Admin",
  OWNER: "Owner",
  MANAGER: "Manager",
  CREW: "Crew",
  TENANT: "Tenant",
  VENDOR: "Vendor",
  VENDOR_CREW: "Vendor Crew",
  APPLICANT: "Applicant",
};