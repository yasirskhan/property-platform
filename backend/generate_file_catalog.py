# generate_file_catalog.py
#
# Walks the project and writes docs/FILE_CATALOG.md - a complete
# inventory of every source file with a summary of what's inside.
#
# Usage:
#   python generate_file_catalog.py
#
# Re-runnable. Overwrites docs/FILE_CATALOG.md each time.
#
# Uses only the Python standard library.
#   - ast  : for Python files (accurate)
#   - re   : for TypeScript / migrations (best effort)
#
# Skips: venv, node_modules, .next, __pycache__, .git, dist, build.

from __future__ import annotations

import ast
import re
from pathlib import Path
from datetime import datetime


ROOT = Path(r"C:\Projects\property-platform")
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PLATFORM_ADMIN = ROOT / "platform-admin"
OUT = ROOT / "docs" / "FILE_CATALOG.md"

SKIP_DIRS = {
    "venv", "node_modules", ".next", "__pycache__", ".git",
    "dist", "build", ".turbo", ".vercel", "coverage",
    ".pytest_cache", ".mypy_cache",
}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def summarize_python(path: Path) -> str:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except Exception as e:
        return f"  - (parse error: {e})\n"

    lines: list[str] = []

    doc = ast.get_docstring(tree)
    if doc:
        first = doc.strip().split("\n")[0].strip()
        lines.append(f'  _"{first}"_\n')

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    async_funcs = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)]

    routes: list[tuple[str, str]] = []
    for n in funcs + async_funcs:
        for d in n.decorator_list:
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute):
                method = d.func.attr.upper()
                if method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                    path_arg = ""
                    if d.args and isinstance(d.args[0], ast.Constant):
                        path_arg = str(d.args[0].value)
                    routes.append((method, path_arg or "/"))

    if classes:
        lines.append("  **Classes:**\n")
        for c in classes:
            bases = ", ".join(
                ast.unparse(b) if hasattr(ast, "unparse") else ""
                for b in c.bases
            )
            doc_c = ast.get_docstring(c)
            first_doc = doc_c.strip().split("\n")[0] if doc_c else ""
            lines.append(f"  - `{c.name}({bases})`{(' - ' + first_doc) if first_doc else ''}")
            methods = [
                m.name for m in c.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not m.name.startswith("_")
            ]
            if methods:
                lines.append(f"    - methods: {', '.join('`' + m + '`' for m in methods)}")
        lines.append("")

    if routes:
        lines.append("  **Routes:**\n")
        for method, p in routes:
            lines.append(f"  - `{method} {p}`")
        lines.append("")

    top_funcs = [f.name for f in funcs + async_funcs if not f.name.startswith("_")]
    if top_funcs:
        lines.append(f"  **Functions:** {', '.join('`' + f + '`' for f in top_funcs)}\n")

    return "\n".join(lines) if lines else "  - (no top-level definitions)\n"


def summarize_typescript(path: Path) -> str:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"  - (read error: {e})\n"

    lines: list[str] = []

    m = re.match(r"\s*//\s*-+\s*\n//\s*(.+)", src)
    if m:
        lines.append(f'  _"{m.group(1).strip()}"_\n')

    exports: list[str] = []

    for m in re.finditer(r"export\s+default\s+function\s+(\w+)", src):
        exports.append(f"default function `{m.group(1)}`")
    for m in re.finditer(r"export\s+(?:async\s+)?function\s+(\w+)", src):
        exports.append(f"function `{m.group(1)}`")
    for m in re.finditer(r"export\s+const\s+(\w+)", src):
        exports.append(f"const `{m.group(1)}`")
    for m in re.finditer(r"export\s+(type|interface)\s+(\w+)", src):
        exports.append(f"{m.group(1)} `{m.group(2)}`")

    if exports:
        lines.append("  **Exports:**\n")
        for e in exports:
            lines.append(f"  - {e}")
        lines.append("")

    locals_ = [
        m.group(1)
        for m in re.finditer(r"^(?:type|interface)\s+(\w+)", src, re.MULTILINE)
    ]
    if locals_:
        lines.append(f"  **Local types:** {', '.join('`' + t + '`' for t in locals_)}\n")

    return "\n".join(lines) if lines else "  - (no exports detected)\n"


def summarize_migration(path: Path) -> str:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"  - (read error: {e})\n"

    lines: list[str] = []
    m = re.search(r'revision\s*=\s*["\']([^"\']+)', src)
    if m:
        lines.append(f"  - revision: `{m.group(1)}`")
    m = re.search(r'down_revision\s*=\s*["\']([^"\']+)', src)
    if m:
        lines.append(f"  - down_revision: `{m.group(1)}`")

    tables = set(re.findall(r'create_table\(\s*["\']([^"\']+)', src))
    tables |= set(re.findall(r'add_column\(\s*["\']([^"\']+)', src))
    tables |= set(re.findall(r'drop_column\(\s*["\']([^"\']+)', src))
    tables |= set(re.findall(r'alter_column\(\s*["\']([^"\']+)', src))
    if tables:
        lines.append(f"  - touches tables: {', '.join('`' + t + '`' for t in sorted(tables))}")

    return "\n".join(lines) + "\n" if lines else "  - (no revision info found)\n"


def walk(base: Path, exts: set[str]) -> list[Path]:
    out = []
    for p in base.rglob("*"):
        if p.is_file() and p.suffix in exts and not should_skip(p.relative_to(ROOT)):
            out.append(p)
    return sorted(out)


def main() -> None:
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("# FILE CATALOG\n")
    lines.append(f"_Auto-generated by `backend/generate_file_catalog.py` on {now}._\n")
    lines.append("Every source file in the project, with a summary of what's inside.")
    lines.append("Re-run `python generate_file_catalog.py` after adding or renaming files.\n")
    lines.append("---\n")

    lines.append("## Backend (Python)\n")
    backend_files = walk(BACKEND, {".py"})
    backend_files = [
        p for p in backend_files
        if not str(p).endswith("generate_file_catalog.py")
    ]

    by_folder: dict[str, list[Path]] = {}
    for p in backend_files:
        folder = rel(p.parent)
        by_folder.setdefault(folder, []).append(p)

    for folder in sorted(by_folder.keys()):
        lines.append(f"### `{folder}/`\n")
        for p in by_folder[folder]:
            lines.append(f"#### `{rel(p)}`\n")
            if "/alembic/versions/" in rel(p).replace("\\", "/"):
                lines.append(summarize_migration(p))
            else:
                lines.append(summarize_python(p))
            lines.append("")

    lines.append("## Frontend (TypeScript / TSX)\n")
    frontend_files = walk(FRONTEND, {".ts", ".tsx"})

    by_folder_f: dict[str, list[Path]] = {}
    for p in frontend_files:
        folder = rel(p.parent)
        by_folder_f.setdefault(folder, []).append(p)

    for folder in sorted(by_folder_f.keys()):
        lines.append(f"### `{folder}/`\n")
        for p in by_folder_f[folder]:
            lines.append(f"#### `{rel(p)}`\n")
            lines.append(summarize_typescript(p))
            lines.append("")

    lines.append("## Platform Admin (TypeScript / TSX)\n")
    platform_admin_files = walk(PLATFORM_ADMIN, {".ts", ".tsx"})

    by_folder_p: dict[str, list[Path]] = {}
    for p in platform_admin_files:
        folder = rel(p.parent)
        by_folder_p.setdefault(folder, []).append(p)

    for folder in sorted(by_folder_p.keys()):
        lines.append(f"### `{folder}/`\n")
        for p in by_folder_p[folder]:
            lines.append(f"#### `{rel(p)}`\n")
            lines.append(summarize_typescript(p))
            lines.append("")

    lines.append("---\n")
    lines.append("## Counts\n")
    lines.append(f"- Backend Python files: {len(backend_files)}")
    lines.append(f"- Customer frontend TS/TSX files: {len(frontend_files)}")
    lines.append(f"- Platform admin TS/TSX files: {len(platform_admin_files)}")
    lines.append(f"- Total: {len(backend_files) + len(frontend_files) + len(platform_admin_files)}\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK - wrote {OUT}")
    print(f"  Backend files:  {len(backend_files)}")
    print(f"  Frontend files: {len(frontend_files)}")
    print(f"  Total:          {len(backend_files) + len(frontend_files)}")


if __name__ == "__main__":
    main()