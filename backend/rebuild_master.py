"""Rebuild PROJECT_MASTER.md by appending the missing sections
(42, 43, 44) and the final END marker to the existing file.
Safe to run multiple times — checks before appending.
"""
from pathlib import Path

PATH = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")

if not PATH.exists():
    print("ERROR: file not found at", PATH)
    raise SystemExit(1)

text = PATH.read_text(encoding="utf-8")

# -----------------------------------------------------------------
# SECTION 42 — Menu Permissions System
# -----------------------------------------------------------------
SECTION_42 = """
---

# SECTION 42 — MENU PERMISSIONS SYSTEM (BUILT)

**Canonical menu keys:** `app/constants/menu_keys.py` on the backend.
46 keys. Format: `PARENT` or `PARENT.CHILD`, uppercase. Frontend
display info (label, href, icon) lives in `src/lib/menuConfig.ts` —
same keys, matched one to one.

**Database tables:**
- `menu_permissions` — one row per (organization_id, role, menu_key).
  Unique constraint on the triple. Column `visible` (bool).
- `user_permissions` — one row per (user_id, menu_key) that represents
  an actual override. Unique on (user_id, menu_key). Columns:
  `visible` (bool), `set_by_user_id` (who set it).
- `sidebar_preferences` — one row per user. Unique on `user_id`.
  Columns: `organization_id`, `order` (JSON array of menu keys),
  `hidden` (JSON array of menu keys).

**Resolver:** `app/services/menu_resolver.py` → `resolve_menu_for_user(db, user)`.
Returns ordered list of `{key, parent}` for keys the user should see.
Hidden items are dropped entirely.

**Endpoints (all under `/api/menu`):**

| Method | Path | Purpose |
|---|---|---|
| GET | `/me` | Resolved sidebar for current user |
| GET | `/roles` | Role matrix (editable subset) |
| PUT | `/roles/{role}` | Bulk-update one role's matrix |
| POST | `/roles/{role}/reset` | Reset one role to defaults |
| GET | `/users` | List users current user can edit |
| GET | `/users/{user_id}` | Overrides for one user |
| PUT | `/users/{user_id}` | Batch-save user overrides |
| DELETE | `/users/{user_id}/overrides` | Clear all overrides for a user |
| GET | `/me/preferences` | Current user's personal prefs |
| PUT | `/me/preferences` | Save current user's personal prefs |

**Frontend pieces:**
- `src/contexts/MenuContext.tsx` — session cache + `refresh()`
- `src/lib/menuPermissions.ts` — typed API client
- `src/lib/menuConfig.ts` — key → label/href/icon
- `src/components/shell/Sidebar.tsx` — reads from MenuContext
- `src/components/permissions/RoleMatrix.tsx` — Roles tab
- `src/components/permissions/UserOverrides.tsx` — Users tab
- `src/components/permissions/MyPreferences.tsx` — My Preferences tab
- `src/app/dashboard/settings/permissions/page.tsx` — 3-tab container

**Seed behavior:** On signup, `create_user` calls
`seed_menu_permissions_for_org` inside the same transaction that creates
the org. Same matrix baked into the `8a3f2c1e9b44` migration for
existing orgs.

**Hard rules (enforced in resolver):**
- Layers 2, 3, 4 can only subtract visibility. Only Layer 1 can grant.
- ADMIN role is immutable: matrix always all-visible, overrides on
  admins ignored.
- Parent hidden → all children hidden.
- Role comparison case-insensitive.
- Every permission change writes to `audit_log`.

**Editor scoping:**
- Admin: everyone below (all roles except ADMIN)
- Owner: MANAGER, CREW, TENANT, VENDOR, VENDOR_CREW, APPLICANT
- Manager: CREW, TENANT, VENDOR, VENDOR_CREW (their scope)
- Crew, Tenant, Vendor, Vendor Crew, Applicant: own prefs only
"""

# -----------------------------------------------------------------
# SECTION 43 — Three-boundary architecture
# -----------------------------------------------------------------
SECTION_43 = """
---

# SECTION 43 — THREE-BOUNDARY ARCHITECTURE

**Boundary 1 — Data isolation (built).** Every customer table has
`organization_id`. Row-level isolation. No cross-tenant leakage.

**Boundary 2 — Identity isolation (partially built).** Two separate
identity systems:
- `users` table — customer side. Every user belongs to exactly one org
  (including ADMIN). Built.
- `platform_users` table — internal side (us). Separate table, separate
  login, separate URL. Built in Phase 9.
- They never mix in a user list, a sidebar, a permission matrix, or a
  login flow.

**Boundary 3 — Commercial channel (Phase 9 + Phase 10).** The only
interface between us and customers:
- Subscriptions (plan, modules, property count)
- Invoices (what we billed them, when)
- Tickets (their messages to us, our replies)
- Provisioning events (org created, module enabled, suspended)
- Usage counters (property count, user count)

These tables contain `organization_id` and platform-owned fields, but no
customer operational data.

**Platform access to customer data:**
- Default: NO. Platform staff see aggregate state, subscription status,
  ticket threads.
- With grant: customer admin grants a time-limited token scoped to a
  ticket. Every action logged. Expires automatically.

**Subscription lifecycle:**
- ACTIVE → PAST_DUE → RESTRICTED → SUSPENDED → CANCELLED
- Enforced at three layers: login gate, API gate (402 for writes), UI gate.
- Automated daily job transitions state based on invoice age.
- Configurable thresholds per plan.
- Stripe webhooks trigger transitions on payment success/failure.
- Manual overrides by platform_admin are logged and time-limited.
- Placeholder is `organizations.state` column (built). Nothing reads it yet.
"""

# -----------------------------------------------------------------
# Append
# -----------------------------------------------------------------
appended = []

if "# SECTION 42 — MENU PERMISSIONS SYSTEM" not in text:
    text = text.rstrip() + "\n" + SECTION_42
    appended.append("Section 42")

if "# SECTION 43 — THREE-BOUNDARY ARCHITECTURE" not in text:
    text = text.rstrip() + "\n" + SECTION_43
    appended.append("Section 43")

if "# END OF PROJECT_MASTER.md" not in text:
    text = text.rstrip() + "\n\n---\n\n# END OF PROJECT_MASTER.md\n"
    appended.append("END marker")

PATH.write_text(text, encoding="utf-8")

print("Appended:", ", ".join(appended) if appended else "(nothing — already present)")
print("File size (bytes):", PATH.stat().st_size)
print("Total lines:", text.count("\n") + 1)