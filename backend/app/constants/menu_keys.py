# ============================================================
# menu_keys.py
# ------------------------------------------------------------
# Single source of truth for every menu key in the app.
#
# Format:  PARENT or PARENT.CHILD
#
# The same list is used by:
#   - the Alembic seed migration (initial row creation)
#   - the backend resolver (Layer 2 checks)
#   - the frontend sidebar (labels + icons, via /api/menu/me)
# ============================================================

# Ordered list of every menu key, parents first, then children.
MENU_KEYS = [
    # ---------- top-level ----------
    "DASHBOARD",
    "CALENDAR",
    "LEASING",
    "PROPERTIES",
    "PEOPLE",
    "ACCOUNTING",
    "MAINTENANCE",
    "REPORTING",
    "COMMUNICATION",
    "WHATS_NEW",
    "SETTINGS",

    # ---------- leasing ----------
    "LEASING.LISTINGS",
    "LEASING.APPLICATIONS",
    "LEASING.CRM",
    "LEASING.TEMPLATES",

    # ---------- properties ----------
    "PROPERTIES.ALL",
    "PROPERTIES.ADD",
    "PROPERTIES.UNITS",
    "PROPERTIES.GROUPS",

    # ---------- people ----------
    "PEOPLE.TEAM",
    "PEOPLE.TENANTS",
    "PEOPLE.OWNERS",
    "PEOPLE.VENDORS",
    "PEOPLE.CONTACTS",

    # ---------- accounting ----------
    "ACCOUNTING.RECEIVABLES",
    "ACCOUNTING.PAYABLES",
    "ACCOUNTING.CHARGES",
    "ACCOUNTING.BANK_ACCOUNTS",
    "ACCOUNTING.JOURNAL_ENTRIES",
    "ACCOUNTING.BANK_TRANSFERS",
    "ACCOUNTING.GL_ACCOUNTS",
    "ACCOUNTING.DIAGNOSTICS",
    "ACCOUNTING.ONLINE_PAYMENTS",
    "ACCOUNTING.DEPOSITS",
    "ACCOUNTING.MANAGEMENT_FEES",
    "ACCOUNTING.OWNER_STATEMENTS",

    # ---------- maintenance ----------
    "MAINTENANCE.WORK_ORDERS",
    "MAINTENANCE.RECURRING",
    "MAINTENANCE.INSPECTIONS",
    "MAINTENANCE.UNIT_TURNS",
    "MAINTENANCE.PROJECTS",
    "MAINTENANCE.PURCHASE_ORDERS",
    "MAINTENANCE.INVENTORY",
    "MAINTENANCE.FIXED_ASSETS",
    "MAINTENANCE.SMART",

    # ---------- reporting ----------
    "REPORTING.ALL",
    "REPORTING.BUILDER",

    # ---------- communication ----------
    "COMMUNICATION.INBOX",
    "COMMUNICATION.MESSAGES",
    "COMMUNICATION.TEMPLATES",
    "COMMUNICATION.SURVEYS",

    # ---------- settings ----------
    "SETTINGS.DISPLAY",
    "SETTINGS.CURRENCIES",
    "SETTINGS.PERMISSIONS",
    "SETTINGS.SIDEBAR",
]


# Every role the system knows about. Stored uppercase in the DB.
ROLES = [
    "ADMIN",
    "OWNER",
    "MANAGER",
    "CREW",
    "TENANT",
    "VENDOR",
    "VENDOR_CREW",
    "APPLICANT",
]


# Default visibility per role. Only the keys listed are visible.
# Anything not listed defaults to False for that role.
DEFAULT_MATRIX = {
    "ADMIN": set(MENU_KEYS),  # admin sees everything
    "OWNER": set(MENU_KEYS) - {"PEOPLE.TEAM", "ACCOUNTING.ONLINE_PAYMENTS"},
    "MANAGER": {
        "DASHBOARD", "CALENDAR",

        "LEASING", "LEASING.LISTINGS", "LEASING.APPLICATIONS",
        "LEASING.CRM", "LEASING.TEMPLATES",

        "PROPERTIES", "PROPERTIES.ALL", "PROPERTIES.ADD",
        "PROPERTIES.UNITS", "PROPERTIES.GROUPS",

        "PEOPLE", "PEOPLE.TENANTS", "PEOPLE.OWNERS",
        "PEOPLE.VENDORS", "PEOPLE.CONTACTS",

        "ACCOUNTING", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.PAYABLES",
        "ACCOUNTING", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.CHARGES",
        "ACCOUNTING.PAYABLES",
        "ACCOUNTING.BANK_ACCOUNTS", "ACCOUNTING.JOURNAL_ENTRIES",
        "ACCOUNTING.BANK_TRANSFERS", "ACCOUNTING.GL_ACCOUNTS",
        "ACCOUNTING.DIAGNOSTICS", "ACCOUNTING.DEPOSITS",
        "ACCOUNTING.MANAGEMENT_FEES", "ACCOUNTING.OWNER_STATEMENTS",

        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS", "MAINTENANCE.RECURRING",
        "MAINTENANCE.INSPECTIONS", "MAINTENANCE.UNIT_TURNS",
        "MAINTENANCE.PROJECTS", "MAINTENANCE.PURCHASE_ORDERS",
        "MAINTENANCE.INVENTORY", "MAINTENANCE.FIXED_ASSETS",
        "MAINTENANCE.SMART",

        "REPORTING", "REPORTING.ALL", "REPORTING.BUILDER",

        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",
        "COMMUNICATION.TEMPLATES", "COMMUNICATION.SURVEYS",

        "WHATS_NEW",
        "SETTINGS", "SETTINGS.DISPLAY",
    },
    "CREW": {
        "DASHBOARD", "CALENDAR",

        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS", "MAINTENANCE.RECURRING",
        "MAINTENANCE.INSPECTIONS", "MAINTENANCE.UNIT_TURNS",

        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",

        "WHATS_NEW",
        "SETTINGS", "SETTINGS.DISPLAY",
    },
    "TENANT": {
        "DASHBOARD",

        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",

        "WHATS_NEW",
        "SETTINGS", "SETTINGS.DISPLAY",
    },
    "VENDOR": {
        "DASHBOARD",

        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS",

        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",

        "WHATS_NEW",
        "SETTINGS", "SETTINGS.DISPLAY",
    },
    "VENDOR_CREW": {
        "DASHBOARD",

        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS",

        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",

        "WHATS_NEW",
        "SETTINGS", "SETTINGS.DISPLAY",
    },
    "APPLICANT": {
        "DASHBOARD",
        "WHATS_NEW",
    },
}


# Roles that a given editor is allowed to edit in the Roles tab.
EDITOR_CAN_EDIT = {
    "ADMIN":     {"OWNER", "MANAGER", "CREW", "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT"},
    "OWNER":     {"MANAGER", "CREW", "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT"},
    "MANAGER":   {"CREW", "TENANT", "VENDOR", "VENDOR_CREW"},
    "CREW":      set(),
    "TENANT":    set(),
    "VENDOR":    set(),
    "VENDOR_CREW": set(),
    "APPLICANT": set(),
}


# Roles for which the role matrix is never editable in the UI.
IMMUTABLE_ROLES = {"ADMIN"}