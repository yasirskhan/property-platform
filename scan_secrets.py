"""Small dependency-free guard for obvious committed secrets.

This is not a replacement for GitHub secret scanning or a dedicated scanner.
It catches several high-confidence credential formats before push/CI.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", ".next", "__pycache__"}
SKIP_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".ico"}

PATTERNS = {
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Stripe secret key": re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{16,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def main() -> int:
    findings: list[tuple[Path, int, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES or ".db.bak_" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append((path.relative_to(ROOT), line, label))

    if findings:
        print("Potential committed secrets detected:")
        for path, line, label in findings:
            print(f"  {path}:{line} — {label}")
        print("Values are intentionally not printed.")
        return 1

    print("Secret-pattern scan CLEAN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
