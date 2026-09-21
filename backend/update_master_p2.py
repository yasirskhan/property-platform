"""
update_master_p2.py
Update Section 11 (migration chain), Section 10 (tables),
Section 57 (audit statuses). Append Sections 58-63.
"""

from pathlib import Path

MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
text = MASTER.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global text
    if old not in text:
        print(f"[skip] {label} — pattern not found")
        return
    text = text.replace(old, new, 1)
    print(f"[ok]   {label}")


# ============================================================
# 1. Section 11 — migration chain update
# ============================================================
replace_once(
    """- 7ca4251074bc_add_bank_accounts
- HEAD: 7ca4251074bc""",
    """- 7ca4251074bc_add_bank_accounts
- e5d4a58b8e85_add_property_amenities
- dadbb391cc03_add_property_appliances
- 35529ce17750_add_property_improvements
- 59a25b856f18_add_phase3_parity_fields
- HEAD: 59a25b856f18""",
    "Section 11 migration chain",
)

# ============================================================
# 2. Section 10 — tables list add Phase 3 tables
# ============================================================
replace_once(
    "Properties: properties, units, property_assignments, property_taxes,\nproperty_tax_payments",
    "Properties: properties, units, property_assignments, property_taxes,\nproperty_amenities, property_appliances, property_improvements,\nproperty_tax_payments",
    "Section 10 tables",
)

# ============================================================
# 3. Section 57 — mark Phase 3 tabs as built
# ============================================================
replace_once(
    """- ⬜ Amenities tab (fee + availability) — Phase 3.5
- ⬜ Appliances tab (condition) — Phase 3.5
- ⬜ Improvements tab (warranty) — Phase 3.5
- ⬜ Photos tab (build it) — Phase 3d""",
    """- ✅ Amenities tab (fee + availability) — done
- ✅ Appliances tab (condition) — done
- ✅ Improvements tab (warranty) — done
- ⬜ Photos tab — Phase 3d
- ⬜ Amenities / Appliances / Improvements attachments — Phase 3.7""",
    "Section 57 statuses",
)

# ============================================================
# 4. Append new sections 58-63 before END marker
# ============================================================
new_sections = """

---

# SECTION 58 — DISPLAY SETTINGS (DESIGNED, NOT YET BUILT)

One page under Settings → Display. Per-user preferences.

Route: /dashboard/settings/display
Menu key: SETTINGS.DISPLAY (added to menu_keys.py in Phase 3.5)

Storage: new table user_display_preferences
- id, user_id (unique), organization_id
- layout_mode: TABS | VERTICAL (default TABS)
- theme: LIGHT | DARK | AUTO (default LIGHT)
- density: COMPACT | COMFORTABLE | SPACIOUS (default COMFORTABLE)
- date_format: US | ISO | EU (default US)
- number_format: US | EU | SPACE (default US)
- font_size: SMALL | NORMAL | LARGE (default NORMAL)
- accent_color: string (nullable)
- reduce_motion: boolean (default false)
- created_at, updated_at

API: GET/PUT /api/settings/display

Frontend:
- Display page: /dashboard/settings/display
- DisplayContext (reads all display settings)
- LayoutContext (reads layout_mode; Property Detail and every
  multi-section page renders either tabs or vertical)
- ThemeContext (reads theme; sets data-theme on <html>)

Behavior:
- Layout mode: "Tabs" = sections at top; "Vertical" = stacked in a
  long scroll (AppFolio-style) with sticky sidebar nav
- Theme: "Light" = current; "Dark" = dark backgrounds;
  "Auto" = follows OS
- Other settings wire up the same way (one column each)

Build order:
- Phase 3.5 — table + endpoint + settings page + contexts;
  wire layout_mode + theme
- Phase 3.6 — density, date format, number format
- Phase 3.7 — font size, accent color, reduce motion

Default for new users: Tabs + Light.

---

# SECTION 59 — PER-ORG CURRENCY (DESIGNED, NOT YET BUILT)

Each customer organization operates in ONE currency.
No exchange, no conversion, no cross-currency transactions.

Currencies supported: USD, EUR, GBP, INR, AUD, CAD, NZD, SGD, AED.

Storage:
- organizations.currency (VARCHAR(3), default "USD")

Formatting:
- Single helper src/lib/money.ts with formatMoney(amount)
- Reads the org's currency from CurrencyContext
- Uses Intl.NumberFormat with the correct locale:
    USD -> en-US -> $1,234.56
    INR -> en-IN -> ₹1,23,456.78 (Indian numbering)
    GBP -> en-GB -> £1,234.56
    EUR -> de-DE -> 1.234,56 €

Refactor:
- Every existing toLocaleString("en-US", { currency: "USD" })
  is replaced with formatMoney(...).
- ~100+ call sites across the frontend.

Where set:
- On signup (default based on their locale)
- Or in Settings → General → Currency (editable once)

Build order:
- Phase 3.5 — organizations.currency + migration + CurrencyContext
  + money.ts helper + Settings General dropdown
- Phase 3.5 — sweep all pages replacing hardcoded USD formatting

Level 3 (true multi-currency with exchange rates) NOT planned.
Deferred indefinitely; only if a real client asks.

---

# SECTION 60 — PROPERTY AMENITIES (BUILT — Phase 3 Step 3a)

AppFolio-parity fields:
- Name (required)
- Category (Building / Unit / Outdoor / Community / Other)
- Notes
- fee_amount (money, optional)
- availability_status: INCLUDED | EXTRA_FEE | NOT_AVAILABLE
- delete_reason (soft-delete pattern)

Table: property_amenities
- id, organization_id, property_id
- name, category, notes
- fee_amount NUMERIC(14,2)
- availability_status VARCHAR(30)
- is_active, delete_reason, created_by_id, timestamps

Migration: e5d4a58b8e85_add_property_amenities
(parity fields added by 59a25b856f18)

Endpoints under /api/properties/{property_id}/amenities:
- GET    ""                    list
- POST   ""                    create
- PATCH  /{amenity_id}         update
- DELETE /{amenity_id}         soft delete

Frontend:
- src/lib/propertyAmenities.ts
- src/components/property/AmenitiesTab.tsx

Remaining gap: Attachments (Phase 3.7).

---

# SECTION 61 — PROPERTY APPLIANCES (BUILT — Phase 3 Step 3b)

AppFolio-parity fields:
- Name (required)
- Brand
- Model #
- Serial #
- Purchase date
- Purchase price
- Warranty expiration
- Condition: NEW | GOOD | FAIR | NEEDS_REPAIR
- Notes
- delete_reason

Table: property_appliances
- id, organization_id, property_id
- name, brand, model_number, serial_number
- purchase_date DATE, purchase_price NUMERIC(14,2)
- warranty_expires DATE
- condition VARCHAR(30)
- notes, is_active, delete_reason, created_by_id, timestamps

Migration: dadbb391cc03_add_property_appliances
(condition + delete_reason added by 59a25b856f18)

Endpoints under /api/properties/{property_id}/appliances:
- GET    ""                     list
- POST   ""                     create
- PATCH  /{appliance_id}        update
- DELETE /{appliance_id}        soft delete

Frontend:
- src/lib/propertyAppliances.ts
- src/components/property/AppliancesTab.tsx

Remaining gap: Attachments (Phase 3.7).

---

# SECTION 62 — PROPERTY IMPROVEMENTS (BUILT — Phase 3 Step 3c)

AppFolio-parity fields:
- improvement_date (required)
- description (required, max 500)
- cost
- contractor
- category (Kitchen / Bath / Roof / HVAC / Flooring / Electrical /
  Plumbing / Exterior / Other)
- warranty_expires
- notes
- delete_reason

Table: property_improvements
- id, organization_id, property_id
- improvement_date DATE, description VARCHAR(500)
- cost NUMERIC(14,2)
- contractor VARCHAR(200), category VARCHAR(60)
- warranty_expires DATE
- notes, is_active, delete_reason, created_by_id, timestamps

Migration: 35529ce17750_add_property_improvements
(warranty_expires + delete_reason added by 59a25b856f18)

Endpoints under /api/properties/{property_id}/improvements:
- GET    ""                       list (newest first)
- POST   ""                       create
- PATCH  /{improvement_id}        update
- DELETE /{improvement_id}        soft delete

Frontend:
- src/lib/propertyImprovements.ts
- src/components/property/ImprovementsTab.tsx

Remaining gaps: Attachments (Phase 3.7), Vendor link (Phase 4).

---

# SECTION 63 — PHASE 3 PARITY MIGRATION (BUILT — 59a25b856f18)

Closed the small gaps found in the AppFolio parity audit.

Added:
- property_amenities.fee_amount
- property_amenities.availability_status
- property_amenities.delete_reason
- property_appliances.condition
- property_appliances.delete_reason
- property_improvements.warranty_expires
- property_improvements.delete_reason
- gl_accounts.must_clear (boolean, default 0)

Purpose:
- fee/availability/condition/warranty close the AppFolio feature
  gaps in the three Phase 3 tabs.
- delete_reason supports the soft-delete-with-reason pattern
  (UI comes in Phase 3.5).
- must_clear powers the REAL "Positive Balance on Fee GL Accounts"
  diagnostic (was placeholder; check wired in Phase 3.6).

Downgrade reverses all of the above.

"""

end_marker = "# END OF PROJECT_MASTER.md"
if end_marker in text:
    text = text.replace(end_marker, new_sections + "\n" + end_marker, 1)
    print("[ok]   Sections 58-63 appended")
else:
    print("[skip] END marker not found")

MASTER.write_text(text, encoding="utf-8")
print(f"Wrote {len(text):,} bytes to {MASTER}")