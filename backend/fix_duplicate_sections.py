"""
fix_duplicate_sections.py
Remove the duplicated Sections 58-63 in PROJECT_MASTER.md.
Keeps the FIRST occurrence of each; removes the second.
"""

from pathlib import Path

MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
text = MASTER.read_text(encoding="utf-8")

# The full duplicate block starts with the second
# "# SECTION 58 — DISPLAY SETTINGS" and ends just before
# "# SECTION 49 — GIT WORKFLOW".

first_58 = text.find("# SECTION 58 — DISPLAY SETTINGS")
second_58 = text.find("# SECTION 58 — DISPLAY SETTINGS", first_58 + 1)

if first_58 == -1:
    print("[skip] Section 58 not found")
elif second_58 == -1:
    print("[ok] No duplicate Section 58 — nothing to remove")
else:
    # Find "# SECTION 49 — GIT WORKFLOW" after the second 58
    section_49 = text.find("# SECTION 49 — GIT WORKFLOW", second_58)
    if section_49 == -1:
        # Fallback: remove from second_58 to END marker
        end_marker = "# END OF PROJECT_MASTER.md"
        section_49 = text.find(end_marker, second_58)
        if section_49 == -1:
            print("[skip] Could not find end of duplicate block")
            raise SystemExit(1)

    before = text[:second_58]
    after = text[section_49:]
    text = before + after
    MASTER.write_text(text, encoding="utf-8")
    print("[ok] Removed duplicate Sections 58-63")
    print(f"Wrote {len(text):,} bytes to {MASTER}")