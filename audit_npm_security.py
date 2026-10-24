#!/usr/bin/env python3
"""Fail npm audits on high/critical findings except explicit dev-only GHSAs.

This exists for advisories that have no patched package release yet. An
exception is accepted only when every advisory leaf is explicitly allowlisted
and every affected package node is marked dev-only in package-lock.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SEVERITY = {"info": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}


def _advisory_leaves(name: str, vulnerabilities: dict, seen: set[str]) -> list[dict]:
    if name in seen:
        return []
    seen = set(seen)
    seen.add(name)
    item = vulnerabilities.get(name)
    if not isinstance(item, dict):
        return [{"url": "", "title": f"Unresolved audit dependency: {name}"}]
    leaves: list[dict] = []
    for via in item.get("via") or []:
        if isinstance(via, str):
            leaves.extend(_advisory_leaves(via, vulnerabilities, seen))
        elif isinstance(via, dict):
            leaves.append(via)
    return leaves


def _is_dev_only(item: dict, packages: dict) -> bool:
    nodes = item.get("nodes") or []
    if not nodes:
        return False
    for node in nodes:
        meta = packages.get(node)
        if not isinstance(meta, dict) or meta.get("dev") is not True:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-file", required=True)
    parser.add_argument("--lock-file", required=True)
    parser.add_argument("--allow-ghsa", action="append", default=[])
    parser.add_argument("--level", default="high", choices=tuple(SEVERITY))
    args = parser.parse_args()

    audit = json.loads(Path(args.audit_file).read_text())
    lock = json.loads(Path(args.lock_file).read_text())
    if audit.get("error"):
        print(f"npm audit returned an error: {audit['error']}", file=sys.stderr)
        return 2

    vulnerabilities = audit.get("vulnerabilities") or {}
    packages = lock.get("packages") or {}
    allowed_ids = set(args.allow_ghsa)
    blockers: list[tuple[str, str, list[str]]] = []
    allowed: list[tuple[str, list[str]]] = []
    threshold = SEVERITY[args.level]

    for name, item in sorted(vulnerabilities.items()):
        severity = str(item.get("severity") or "").lower()
        if SEVERITY.get(severity, 99) < threshold:
            continue

        leaves = _advisory_leaves(name, vulnerabilities, set())
        urls = [str(leaf.get("url") or "") for leaf in leaves]
        leaf_ids = {
            url.rstrip("/").split("/")[-1]
            for url in urls
            if "github.com/advisories/" in url
        }
        explicitly_allowed = bool(leaves) and leaf_ids and leaf_ids <= allowed_ids
        if explicitly_allowed and _is_dev_only(item, packages):
            allowed.append((name, sorted(leaf_ids)))
            continue
        blockers.append((name, severity, sorted(leaf_ids)))

    for name, ids in allowed:
        print(
            "ALLOW dev-only unpatched npm advisory chain: "
            f"{name} -> {', '.join(ids)}"
        )

    if blockers:
        print("Blocking npm audit findings:", file=sys.stderr)
        for name, severity, ids in blockers:
            suffix = f" ({', '.join(ids)})" if ids else ""
            print(f"- {name}: {severity}{suffix}", file=sys.stderr)
        return 1

    print("npm audit policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
