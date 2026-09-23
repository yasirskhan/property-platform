"""One-command project verification for a non-coder workflow.

Run from the repository root with `python verify_project.py` or `verify.bat`.
CI remains authoritative for Python 3.12 + PostgreSQL.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def backend_python() -> str:
    candidates = [
        BACKEND / "venv" / "Scripts" / "python.exe",
        BACKEND / "venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run(label: str, command: list[str], cwd: Path) -> None:
    print("\n" + "=" * 72)
    print(label)
    print("=" * 72)
    print(" ".join(command))
    result = subprocess.run(command, cwd=cwd)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Skip the production frontend build")
    args = parser.parse_args()

    py = backend_python()
    run("1/5 Planning consistency", [py, "check_parity.py"], BACKEND)
    run("2/5 Secret-pattern scan", [sys.executable, "scan_secrets.py"], ROOT)
    run("3/5 Backend tests", [py, "-m", "pytest", "-q", "-m", "not e2e"], BACKEND)

    if args.backend_only:
        print("\nVERIFIED: requested backend-only checks passed.")
        return 0

    npm = shutil.which("npm")
    if not npm:
        print("ERROR: npm is not available on PATH.")
        return 2
    if not (FRONTEND / "node_modules").exists():
        print("ERROR: frontend/node_modules is missing. Run `npm ci` in frontend first.")
        return 2

    run("4/5 Frontend lint", [npm, "run", "lint"], FRONTEND)
    run("4/5 Frontend TypeScript", [npm, "run", "typecheck"], FRONTEND)
    if not args.quick:
        run("5/5 Frontend production build", [npm, "run", "build"], FRONTEND)

    print("\nVERIFIED: all requested local checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
