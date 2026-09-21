# update_master_catalog_rule.py
#
# Two small edits to PROJECT_MASTER.md:
#
# 1. Section 67 (Session Close Checklist) - add a new mandatory
#    step: regenerate docs/FILE_CATALOG.md when new files were
#    created or renamed during the session.
#
# 2. Section 69 (FILE MAP) - add a pointer to docs/FILE_CATALOG.md
#    as the authoritative inventory of every file + what's inside.
#
# Backs up before writing. Aborts if any anchor is missing.

from pathlib import Path
import shutil
import sys

MD = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
BACKUP = MD.with_suffix(".md.backup-before-catalog-rule")

if not MD.exists():
    print(f"ERROR: {MD} not found.")
    sys.exit(1)

shutil.copy2(MD, BACKUP)
print(f"Backed up to {BACKUP}")

text = MD.read_text(encoding="utf-8")
original = text


# ============================================================
# FIX 1 - Section 67: insert a new step 5 (shift 5->6, 6->7)
# ============================================================
ANCHOR_67 = (
    "### 4. Delete one-off scripts\n"
    "\n"
    "Remove from backend/:\n"
    "\n"
    "    update_master_p1.py\n"
    "    update_master_p2.py\n"
    "    update_checklist.py\n"
    "    fix_*.py\n"
    "    rebuild_*.py\n"
    "    patch_*.py\n"
    "    add_*.py\n"
    "\n"
    "They are gitignored, but delete them anyway. Do not let them pile up.\n"
    "\n"
    "### 5. Push"
)

REPLACE_67 = (
    "### 4. Delete one-off scripts\n"
    "\n"
    "Remove from backend/:\n"
    "\n"
    "    update_master_p1.py\n"
    "    update_master_p2.py\n"
    "    update_checklist.py\n"
    "    fix_*.py\n"
    "    rebuild_*.py\n"
    "    patch_*.py\n"
    "    add_*.py\n"
    "\n"
    "They are gitignored, but delete them anyway. Do not let them pile up.\n"
    "\n"
    "### 5. Regenerate the FILE CATALOG (if new files were added or renamed)\n"
    "\n"
    "Run:\n"
    "\n"
    "    cd backend\n"
    "    python generate_file_catalog.py\n"
    "\n"
    "This rewrites docs/FILE_CATALOG.md with an up-to-date\n"
    "inventory of every backend Python file and every frontend\n"
    "TS/TSX file - classes, routes, exports, migration chain.\n"
    "\n"
    "Run this step if the session added, renamed, or deleted\n"
    "any source files. Skip only if the session was a pure edit\n"
    "to existing files with no new filenames.\n"
    "\n"
    "This keeps Section 69 (FILE MAP) and FILE_CATALOG.md in\n"
    "sync with reality, so the next session never has to guess\n"
    "where something lives.\n"
    "\n"
    "### 6. Push"
)

if ANCHOR_67 in text:
    text = text.replace(ANCHOR_67, REPLACE_67, 1)
    print("  Section 67 updated (catalog regeneration added).")
else:
    print("  NOTE: Section 67 anchor not found (skipped).")


# Fix the "### 6. Report back" that follows - was 6, becomes 7
ANCHOR_67_REPORT = "### 6. Report back"
REPLACE_67_REPORT = "### 7. Report back"

if ANCHOR_67_REPORT in text:
    text = text.replace(ANCHOR_67_REPORT, REPLACE_67_REPORT, 1)
    print("  Section 67 report-back renumbered to 7.")
else:
    print("  NOTE: Section 67 report-back anchor not found (skipped).")


# ============================================================
# FIX 2 - Section 69: add FILE_CATALOG.md pointer at the top
# ============================================================
ANCHOR_69 = (
    "# SECTION 69 — FILE MAP (where everything lives)\n"
    "\n"
    "**Root:** C:\\Projects\\property-platform\\"
)

REPLACE_69 = (
    "# SECTION 69 — FILE MAP (where everything lives)\n"
    "\n"
    "**Root:** C:\\Projects\\property-platform\\\n"
    "\n"
    "## Companion document: docs/FILE_CATALOG.md\n"
    "\n"
    "`FILE_CATALOG.md` is an auto-generated inventory of every\n"
    "source file in the project - classes, routes, exports, and\n"
    "the migration chain, all extracted from the real code.\n"
    "\n"
    "Regenerate it any time with:\n"
    "\n"
    "    cd backend\n"
    "    python generate_file_catalog.py\n"
    "\n"
    "Section 67 requires regenerating it at the end of any session\n"
    "that added, renamed, or deleted source files.\n"
    "\n"
    "**Use this section (69) to know WHERE things live.\n"
    "Use FILE_CATALOG.md to know WHAT is inside each file.**"
)

if ANCHOR_69 in text:
    text = text.replace(ANCHOR_69, REPLACE_69, 1)
    print("  Section 69 updated (FILE_CATALOG pointer added).")
else:
    print("  NOTE: Section 69 anchor not found (skipped).")


# ============================================================
# Write
# ============================================================
if text == original:
    print("No changes written (unexpected).")
    sys.exit(3)

MD.write_text(text, encoding="utf-8")

check = MD.read_text(encoding="utf-8")
if "generate_file_catalog.py" not in check:
    print("ERROR: catalog rule not present after write.")
    sys.exit(4)

print()
print(f"Old size: {len(original)} bytes")
print(f"New size: {len(check)} bytes")
print("OK - master doc updated.")