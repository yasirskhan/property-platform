"""Static navigation integrity check.

This protects the customer menu contract without requiring every dashboard
page to appear in the sidebar. Canonical menu keys may be planned years ahead,
but any leaf route that is currently resolved must have a real page source.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from app.constants.menu_keys import MENU_KEYS, MENU_ROUTE_BLOCKED_UNTIL
from app.services.report_catalog import REPORT_CATALOG

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MENU_CONFIG = PROJECT_ROOT / "frontend" / "src" / "lib" / "menuConfig.ts"
FRONTEND_APP = PROJECT_ROOT / "frontend" / "src" / "app"

ENTRY_RE = re.compile(
    r'(?:"(?P<quoted>[^"]+)"|(?P<plain>[A-Z_]+)):\s*\{\s*'
    r'key:\s*"(?P<key>[^"]+)",\s*label:\s*"(?P<label>[^"]+)",\s*'
    r'href:\s*"(?P<href>[^"]+)"'
)


def _entries() -> dict[str, dict[str, str]]:
    text = MENU_CONFIG.read_text(encoding="utf-8")
    result: dict[str, dict[str, str]] = {}
    for match in ENTRY_RE.finditer(text):
        key = match.group("key")
        result[key] = {
            "label": match.group("label"),
            "href": match.group("href"),
        }
    return result


def _page_for(href: str) -> Path:
    path = urlsplit(href).path
    return FRONTEND_APP / path.lstrip("/") / "page.tsx"


def main() -> int:
    errors: list[str] = []
    entries = _entries()
    backend_keys = set(MENU_KEYS)
    frontend_keys = set(entries)

    for key in sorted(backend_keys - frontend_keys):
        errors.append(f"Backend menu key has no frontend rendering entry: {key}")
    for key in sorted(frontend_keys - backend_keys):
        errors.append(f"Frontend menu key is absent from backend contract: {key}")

    unknown_blocked = set(MENU_ROUTE_BLOCKED_UNTIL) - backend_keys
    for key in sorted(unknown_blocked):
        errors.append(f"Route-readiness map references unknown menu key: {key}")

    parents = {key.split(".", 1)[0] for key in MENU_KEYS if "." in key}

    missing_leaf_routes: list[str] = []
    for key in MENU_KEYS:
        entry = entries.get(key)
        if entry is None:
            continue
        if key in parents:
            # Containers expand/collapse in Sidebar; their configured href is
            # not itself a customer destination while children are visible.
            continue
        page = _page_for(entry["href"])
        if not page.exists():
            missing_leaf_routes.append(key)
            if key not in MENU_ROUTE_BLOCKED_UNTIL:
                errors.append(
                    f"Navigable menu key has no page and is not fail-closed: "
                    f"{key} -> {entry['href']}"
                )

    for key in sorted(MENU_ROUTE_BLOCKED_UNTIL):
        if key in parents:
            continue
        entry = entries.get(key)
        if entry is None:
            continue
        page = _page_for(entry["href"])
        if page.exists():
            errors.append(
                f"Blocked menu route now has page source; review and remove its "
                f"readiness block when verified: {key} -> {entry['href']}"
            )

    for report in REPORT_CATALOG:
        if not report.available or not report.href:
            continue
        page = _page_for(report.href)
        if not page.exists():
            errors.append(
                f"Available report has no page source: {report.key} -> {report.href}"
            )

    print("=" * 68)
    print("NAVIGATION INTEGRITY")
    print("=" * 68)
    print(f"Backend menu keys:       {len(backend_keys)}")
    print(f"Frontend menu entries:   {len(frontend_keys)}")
    print(f"Blocked-until-ready:     {len(MENU_ROUTE_BLOCKED_UNTIL)}")
    print(f"Missing leaf routes:     {len(missing_leaf_routes)}")
    print(f"Available report links:  {sum(1 for r in REPORT_CATALOG if r.available and r.href)}")
    if errors:
        print("=" * 68)
        print(f"FAILURES: {len(errors)}")
        print("=" * 68)
        for error in errors:
            print(f"  - {error}")
        return 1
    print("=" * 68)
    print("CLEAN — every exposed menu/report destination has a real page source.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
