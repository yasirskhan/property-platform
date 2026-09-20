from pathlib import Path

P = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
text = P.read_text(encoding="utf-8")

print("=== FILE STATS ===")
print("Total lines:", text.count("\n") + 1)
print("Total bytes:", len(text.encode("utf-8")))

print()
print("=== KEY MARKERS ===")
markers = [
    "Last updated:",
    "A1. WHERE WE ARE RIGHT NOW",
    "Current activity:",
    "B1. IMMEDIATE NEXT ACTION",
    "# END OF PART A + PART B",
    "# SECTION 1 — PROJECT IDENTITY",
    "# SECTION 12 — THE",
    "# SECTION 42 — MENU PERMISSIONS SYSTEM",
    "# SECTION 43 — THREE-BOUNDARY",
    "# SECTION 44 — GENERAL LEDGER",
    "# END OF PROJECT_MASTER.md",
]
for m in markers:
    found = m in text
    print(f"  [{'x' if found else ' '}] {m}")

print()
print("=== '57' occurrences ===")
for i, line in enumerate(text.split("\n"), 1):
    if "57" in line:
        print(f"  line {i}: {line[:100]}")

print()
print("=== LAST 5 LINES ===")
for line in text.split("\n")[-5:]:
    print("  |", line)