"""
update_master_p1.py
Update PROJECT_MASTER.md — Part A + Part B with current session's work.
"""

from pathlib import Path

MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
text = MASTER.read_text(encoding="utf-8")


def replace_block(text, start_marker, end_marker, new_block, label):
    i = text.find(start_marker)
    if i == -1:
        print(f"[skip] {label} — start marker not found")
        return text
    j = text.find(end_marker, i)
    if j == -1:
        print(f"[skip] {label} — end marker not found")
        return text
    return text[: i + len(start_marker)] + new_block + text[j:]


new_part_a = """

## A1. WHERE WE ARE RIGHT NOW

**Current activity:** Phase 3 (Property Detail tabs). Steps 3a, 3b, 3c
COMPLETE. All Phase 3 tabs now match AppFolio (except Attachments,
deferred to Phase 3.7). Next: 3d (Photos).

**Last completed work (this session):**
- Phase 3 Step 3a (Amenities) — added `fee_amount` and
  `availability_status` to match AppFolio.
- Phase 3 Step 3b (Appliances) — added `condition` to match AppFolio.
- Phase 3 Step 3c (Improvements) — added `warranty_expires` to match
  AppFolio.
- Universal `delete_reason` — added to property_amenities,
  property_appliances, property_improvements.
- `gl_accounts.must_clear` — added for the real Positive Fee diagnostic.
- Migration HEAD now: `59a25b856f18_add_phase3_parity_fields`.
- Section 57 (AppFolio Feature Parity Audit) added — 100+ items.
- Section 38 rebuilt with Phases 3.5, 3.6, 3.7, 4.5.

**What's NOT built yet (designed, not coded):**
- Phase 3d: Photos tab (upload, cover flag, marketing flag, bulk
  upload, captions, sort, styled delete modal). No image editor —
  that's Phase 3.5.
- Display settings — one page under Settings with Layout mode
  (Tabs vs Vertical), Theme (Light/Dark/Auto), Density, Date format,
  Number format, Currency format, Font size, Accent color, Reduce
  motion. Layout + Theme wired first; rest are shown as "Coming soon"
  but their table columns exist so no re-migration is needed.
- Per-org currency — each customer uses their own currency end-to-end.
  No exchange, no conversion. Org picks INR / USD / GBP / EUR / etc.
- All Phase 3.5, 3.6, 3.7, 4, 4.5, 5-12 items — see Section 38.

**Customer-facing impact:**
- Attachments (Phase 3.7) and Vendor link (Phase 4) are the only
  remaining gaps on the Amenities/Appliances/Improvements tabs.
- Display settings + per-org currency are what international clients
  (India, UK, EU) will look for first.
- All gaps are scheduled in this doc. Nothing is unplanned.

## A2. WHAT'S BUILT (WORKING)

- Sessions 1-17 (auth, properties, units, people, leases, work
  orders, password reset, org email, uploads, team UI, property
  detail tabs, financials, taxes, policies, utilities, insurance,
  expenses, income, tenant insurance, applicant role, screening,
  OCR settings)
- Phase 1 — Menu Permissions System (4-layer gating, full UI)
- Phase 2 Step 1 — Chart of Accounts (61 accounts, CRUD, UI)
- Phase 2 Step 2 — General Ledger
- Phase 2 Step 2b — Manual Journal Entry
- Phase 2 Step 4 — Bank Accounts (Client Trust + Security Deposit Trust)
- Phase 2 Step 5 — Receipts (tenant / owner / other + reversal)
- Phase 2 Step 6 — Bills (two-step accrual)
- Phase 2 Step 7 — Bank Deposits
- Phase 2 Step 8a — Owner Sub-Ledger Foundation
- Phase 2 Step 8b — Financial Diagnostics (six checks)
- Phase 2 Step 9 — Management Fees (two-step: creates a Bill)
- Phase 2 Step 10 — Owner Statements (frozen snapshots, print-ready)
- Phase 3 Step 3a — Amenities (fee + availability)
- Phase 3 Step 3b — Appliances (condition)
- Phase 3 Step 3c — Improvements (warranty_expires)

## A3. TECH STACK

Backend:
- Python 3.12 + FastAPI
- SQLAlchemy ORM
- SQLite (dev) -> PostgreSQL (production on AWS RDS)
- Alembic for migrations (hand-written only, never autogenerate)
- JWT auth, bcrypt==4.0.1 (pinned)

Frontend (web):
- Next.js 16.3.5 (App Router, Turbopack in dev)
- React 19, TypeScript, Tailwind CSS
- lucide-react, @dnd-kit

Frontend (mobile — Phase 12, planned):
- React Native / Expo

Environment:
- Windows 11, PowerShell, VS Code
- Node v24.19.0, npm 11.17.0

Deployment target (Phase 11):
- AWS (Lightsail + RDS Postgres for launch; migrate to ECS Fargate later)
- S3 for file uploads
- CloudFront for CDN

## A4. WORKING RULES

1. User is a non-coder. Never ask them to write code. Give whole files, not fragments.
2. Every command must be labelled BACKEND or FRONTEND.
3. Every file must be given whole. Never "add this line."
4. User runs commands and reports back. If error, they paste it.
5. One step at a time. Never give 5 steps at once.
6. Backend commands from C:\\Projects\\property-platform\\backend. Venv is at backend\\venv (NOT .venv). Activate: .\\venv\\Scripts\\Activate.ps1
7. Frontend commands from C:\\Projects\\property-platform\\frontend.
8. Test accounts (all use test1234):
   - admin@test.com (ADMIN)
   - owner1@test.com (OWNER)
   - manager1@test.com (MANAGER)
   - crew1@test.com (CREW)
   - tenant1@test.com (TENANT)
9. Never use Alembic autogenerate. Write migrations by hand.
10. Back up DB before risky migrations. DB is property_platform.db.
11. Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
12. If Next.js 404s on pages that exist, check for stray frontend\\app folder.
13. Every GL posting goes through post_transaction(). Never write to GL tables directly.
14. GL account seed count: 61 per org (60 original + 2100 AP added in Step 6).
15. `push.bat` on the desktop is the one-click way to save to GitHub.

## A5. CURRENT OPEN DECISIONS

- Auto-description rules for Receipt lines: rent rows get
  "{Month} rent", fee rows get "{Fee} — {tenant}". Revisit later.
- Bill auto-description: not yet built.
- Reverse confirmation uses styled modal on Amenities/Appliances/
  Improvements. Still window.confirm() on Receipts/Bills/etc. Roll
  out styled modal everywhere during Phase 3.5.
- Back-navigation: Trial Balance and Deposits have smart-back.
  Roll out to Receipts/Bills/GL Accounts during Phase 3.5.
- Mobile: desktop-first for manager app; portals mobile-first
  (Phase 7); native app = Phase 12.
- Bank Deposits do NOT post to the GL. If we later add a "cash on
  hand" GL account, add DR Bank / CR Cash on Hand in create_deposit().
- Diagnostics currently detect only. Auto-fix postings deferred
  to Phase 3.6.
- Display settings (Section 58) and per-org currency (Section 59)
  captured as new sections — build order in Phase 3.5.
- Section 12 says 61 GL accounts; header comment in gl_account.py
  still says 57. Fix in the next cleanup pass.
"""

text = replace_block(
    text,
    "# PART A — CURRENT STATE",
    "# ═══════════════════════════════════════════════════\n# PART B",
    new_part_a,
    "Part A",
)

new_part_b = """

## B1. IMMEDIATE NEXT ACTION

**Continue Phase 3 — Step 3d (Photos), then Display settings.**

Order:
1. Step 3d: Photos tab (upload, cover flag, marketing flag, bulk
   upload, captions, sort, styled delete modal). No image editor —
   that's Phase 3.5.
2. Display settings section (Section 58) + per-org currency
   (Section 59) — build the infrastructure first so Photos and
   every future module inherits both.
3. Close Phase 3 — master doc check + commit.

## B2. AFTER THAT (Phase 3.5 onward)

See Section 38 for the full build order including:
- Phase 3.5 — Property Detail Polish
- Phase 3.6 — Accounting Polish
- Phase 3.7 — Reports + Universal Attachments
- Phase 4 — Vendors
- Phase 4.5 — Compliance (HOA / Affordable / Commercial / RUBs)
- Phases 5-12

## B3. AFTER PHASE 3

See Section 38.
"""
text = replace_block(
    text,
    "## B1. IMMEDIATE NEXT ACTION",
    "\n---\n\n# ═══════════════════════════════════════════════════\n# END OF PART A + PART B",
    new_part_b,
    "Part B1-B3",
)

MASTER.write_text(text, encoding="utf-8")
print("[ok] Part A + Part B updated")
print(f"Wrote {len(text):,} bytes to {MASTER}")