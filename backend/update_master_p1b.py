"""
update_master_p1b.py
Replace Part B (B1-B4) in PROJECT_MASTER.md.
"""

from pathlib import Path

MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
text = MASTER.read_text(encoding="utf-8")

start = "## B1. IMMEDIATE NEXT ACTION"
end = "# END OF PART A + PART B"

i = text.find(start)
j = text.find(end, i)

if i == -1:
    print("[skip] B1 start not found")
elif j == -1:
    print("[skip] END marker not found")
else:
    new_b = """## B1. IMMEDIATE NEXT ACTION

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
- Phases 5-12 (Smart Maintenance, Messaging, Portals, Integrations,
  Internal Team, Billing, Production, Mobile)

## B3. AFTER PHASE 3

See Section 38.

## B4. HOW TO RESUME IN A NEW CHAT

Paste this to any new assistant:

I'm continuing to build a property management platform (AppFolio clone).

Read this PROJECT_MASTER.md file fully. It has three parts:
- Part A: Current state
- Part B: Next action
- Part C: Full reference

Then continue from the immediate next action listed in Part B1.

Rules you must follow:
- I am a non-coder. Never ask me to write code.
- Give whole files, not fragments. I select-all, delete, paste, save.
- Label every command BACKEND or FRONTEND.
- One step at a time. Wait for me to run and report back.
- If I paste an error, fix it and give the next command.
- Backend venv is at backend\\venv (not .venv). DB is property_platform.db.
- Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
- Every GL posting goes through post_transaction().

Then paste this entire file.

"""
    text = text[:i] + new_b + text[j:]
    MASTER.write_text(text, encoding="utf-8")
    print("[ok] Part B1-B4 replaced")
    print(f"Wrote {len(text):,} bytes to {MASTER}")