"""
check_parity.py — planning/coverage consistency checker.

Checks two authoritative planning artifacts:
  1. docs/APPFOLIO_PARITY_CHECKLIST.json
  2. docs/FEATURE_REGISTRY.md

This script proves planning consistency only. It does NOT prove that a
workflow behaves correctly. Behavioral proof belongs to the automated
checks in the Engineering Safety Foundation.

Usage (from repository root or backend folder):
    python backend/check_parity.py
    python check_parity.py

Exit code:
    0 = clean planning/registry consistency
    1 = one or more consistency failures
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKLIST_PATH = PROJECT_ROOT / "docs" / "APPFOLIO_PARITY_CHECKLIST.json"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "FEATURE_REGISTRY.md"
FRONTEND_APP_ROOT = PROJECT_ROOT / "frontend" / "src" / "app"

VALID_STATUSES = {"built", "in_progress", "scheduled", "planned_no_phase", "unplanned"}
BAD_STATUSES = {"planned_no_phase", "unplanned"}
REGISTRY_STATUS_MARKERS = ("✅", "⬜", "❌")
ROUTINE_TYPES_WITHOUT_RELEASE_GATES = {
    "field",
    "fields",
    "column",
    "columns",
    "filter",
    "filters",
    "label",
    "labels",
    "row",
    "control",
    "controls",
    "navigation",
}


def clean_cell(value: str) -> str:
    value = value.strip()
    value = value.replace("`", "")
    return value


def parse_registry_tables(text: str) -> tuple[list[dict[str, str]], list[str]]:
    """Return normalized surface rows plus structural errors."""
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    lines = text.splitlines()

    expected_header = [
        "Slot",
        "Type",
        "Release gate",
        "Entitlement",
        "Org config",
        "Permission",
        "User hide",
        "Status",
        "Notes",
    ]

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("| Slot | Type | Release gate |"):
            i += 1
            continue

        header = [c.strip() for c in line.strip("|").split("|")]
        if header != expected_header:
            errors.append(f"Registry table at line {i + 1} has unexpected header: {header}")
            i += 1
            continue

        if i + 1 >= len(lines) or not lines[i + 1].strip().startswith("|---"):
            errors.append(f"Registry table at line {i + 1} is missing separator row")
            i += 1
            continue

        i += 2
        while i < len(lines):
            raw = lines[i].strip()
            if not raw.startswith("|"):
                break
            cells = [c.strip() for c in raw.strip("|").split("|")]
            if len(cells) != len(expected_header):
                errors.append(
                    f"Registry row at line {i + 1} has {len(cells)} cells; expected {len(expected_header)}"
                )
                i += 1
                continue
            row = dict(zip(expected_header, cells))
            row["_line"] = str(i + 1)
            rows.append(row)
            i += 1

    return rows, errors


def extract_registry_routes(text: str) -> list[str]:
    routes: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("**Route:**") or stripped.startswith("**Routes:**"):
            for route in re.findall(r"`(/dashboard[^`]*)`", stripped):
                routes.append(route)
    return routes


def route_to_page_file(route: str) -> Path:
    relative = route.lstrip("/")
    return FRONTEND_APP_ROOT / relative / "page.tsx"


def validate_checklist() -> tuple[list[str], Counter, list[dict]]:
    errors: list[str] = []
    if not CHECKLIST_PATH.exists():
        return [f"{CHECKLIST_PATH} not found"], Counter(), []

    try:
        data = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Could not parse parity JSON: {exc}"], Counter(), []

    items = data.get("items")
    if not isinstance(items, list):
        return ["Parity JSON must contain an items array"], Counter(), []

    counts = Counter(item.get("status") for item in items)
    meta = data.get("_meta", {})
    expected_meta = {
        "total_items": len(items),
        "built_count": counts.get("built", 0),
        "scheduled_count": counts.get("scheduled", 0),
        "in_progress_count": counts.get("in_progress", 0),
    }
    for key, actual in expected_meta.items():
        if meta.get(key) != actual:
            errors.append(
                f"Parity _meta.{key}={meta.get(key)!r} does not match actual value {actual}"
            )

    seen_ids: set[str] = set()
    for item in items:
        item_id = item.get("id", "(missing id)")
        status = item.get("status")
        if item_id in seen_ids:
            errors.append(f"Duplicate parity id: {item_id}")
        seen_ids.add(item_id)

        if status not in VALID_STATUSES:
            errors.append(f"Unknown status {status!r} on {item_id}")

        if status in BAD_STATUSES:
            errors.append(f"[{status}] {item_id}: {item.get('feature', '')}")

        if status in {"built", "scheduled", "in_progress"} and not item.get("phase"):
            errors.append(f"Missing phase on {item_id} ({status})")

    return errors, counts, items


def validate_registry() -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    stats = {"routes": 0, "surface_rows": 0, "release_gates": 0}

    if not REGISTRY_PATH.exists():
        return [f"{REGISTRY_PATH} not found"], stats

    text = REGISTRY_PATH.read_text(encoding="utf-8")
    rows, table_errors = parse_registry_tables(text)
    errors.extend(table_errors)
    stats["surface_rows"] = len(rows)

    routes = extract_registry_routes(text)
    stats["routes"] = len(routes)
    for route in routes:
        page_file = route_to_page_file(route)
        if not page_file.exists():
            errors.append(f"Registry route has no page source: {route} -> {page_file.relative_to(PROJECT_ROOT)}")

    release_gates: set[str] = set()
    for row in rows:
        line_no = row["_line"]
        slot = clean_cell(row["Slot"])
        slot_type = clean_cell(row["Type"]).lower()
        gate = clean_cell(row["Release gate"])
        org_config = clean_cell(row["Org config"]).lower()
        user_hide = clean_cell(row["User hide"]).lower()
        status = clean_cell(row["Status"])

        if not any(status.startswith(marker) for marker in REGISTRY_STATUS_MARKERS):
            errors.append(f"Registry line {line_no} ({slot}) has invalid status marker: {status}")

        if gate not in {"—", "-", ""}:
            if not gate.startswith("release."):
                errors.append(f"Registry line {line_no} ({slot}) release gate must start with 'release.': {gate}")
            release_gates.add(gate)

        if slot_type in ROUTINE_TYPES_WITHOUT_RELEASE_GATES and gate not in {"—", "-", ""}:
            errors.append(
                f"Registry line {line_no} ({slot}) is routine type '{slot_type}' but has release gate {gate}"
            )

        if org_config not in {"yes", "no", "—", "-", ""}:
            errors.append(f"Registry line {line_no} ({slot}) invalid Org config value: {row['Org config']}")

        if user_hide not in {"yes", "no", "—", "-", ""}:
            errors.append(f"Registry line {line_no} ({slot}) invalid User hide value: {row['User hide']}")

    stats["release_gates"] = len(release_gates)
    return errors, stats


def main() -> int:
    checklist_errors, counts, items = validate_checklist()
    registry_errors, registry_stats = validate_registry()
    errors = checklist_errors + registry_errors

    print("=" * 68)
    print("PROJECT PARITY / REGISTRY CONSISTENCY")
    print("=" * 68)
    print(f"Parity items:   {len(items)}")
    print(f"  built:        {counts.get('built', 0)}")
    print(f"  in_progress:  {counts.get('in_progress', 0)}")
    print(f"  scheduled:    {counts.get('scheduled', 0)}")
    print(f"  phase-less:   {counts.get('planned_no_phase', 0)}")
    print(f"  unplanned:    {counts.get('unplanned', 0)}")
    print()
    print("Feature Registry:")
    print(f"  current routes declared: {registry_stats['routes']}")
    print(f"  surface rows:            {registry_stats['surface_rows']}")
    print(f"  unique release gates:    {registry_stats['release_gates']}")
    print()

    if errors:
        print("=" * 68)
        print(f"FAILURES: {len(errors)}")
        print("=" * 68)
        for error in errors:
            print(f"  - {error}")
        return 1

    print("=" * 68)
    print("CLEAN — planning inventory and Feature Registry are structurally consistent.")
    print("NOTE: CLEAN is not behavioral proof; automated tests provide that evidence.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())