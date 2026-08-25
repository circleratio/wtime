"""Generate portable/wtime.py, a single-file build of the wtime package.

Run as: python3 scripts/build_portable.py
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "wtime"
OUTPUT = ROOT / "portable" / "wtime.py"

MODULE_ORDER = ["clock.py", "formatter.py", "cli.py"]

HEADER = (
    "# This file is auto-generated from src/wtime/ by scripts/build_portable.py.\n"
    "# Do not edit directly.\n"
)

FOOTER = '\nif __name__ == "__main__":\n    sys.exit(main())\n'


def _is_internal_import(node: ast.stmt) -> bool:
    if isinstance(node, ast.ImportFrom):
        return node.module is not None and node.module.split(".")[0] == "wtime"
    if isinstance(node, ast.Import):
        return all(alias.name.split(".")[0] == "wtime" for alias in node.names)
    return False


def split_module(path: Path):
    """Return (external_import_lines, body_source) for a module file."""
    source = path.read_text()
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    import_lines = []
    body_ranges = []  # (kind, start_line, end_line) 0-indexed, exclusive end
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if not _is_internal_import(node):
                import_lines.append(
                    "".join(lines[node.lineno - 1 : node.end_lineno])
                )
            body_ranges.append(("skip", node.lineno - 1, node.end_lineno))
        else:
            start_lineno = node.lineno
            decorators = getattr(node, "decorator_list", None)
            if decorators:
                start_lineno = decorators[0].lineno
            body_ranges.append(("keep", start_lineno - 1, node.end_lineno))

    body_parts = []
    for kind, start, end in body_ranges:
        if kind == "keep":
            body_parts.append("".join(lines[start:end]))
    body = "\n\n".join(part.rstrip("\n") for part in body_parts)
    return import_lines, body.strip("\n")


_IMPORT_RE = re.compile(r"^from (\S+) import (.+)$")


def merge_imports(import_lines):
    """Merge a list of raw import source snippets into deduped statements."""
    plain_imports = set()
    from_imports = {}  # module -> set(names)
    for snippet in import_lines:
        text = snippet.strip()
        text = text.replace("(", "").replace(")", "")
        text = " ".join(text.split())
        if text.startswith("import "):
            plain_imports.add(text)
            continue
        match = _IMPORT_RE.match(text)
        if not match:
            continue
        module, names = match.groups()
        names = {n.strip() for n in names.rstrip(",").split(",") if n.strip()}
        from_imports.setdefault(module, set()).update(names)

    lines = sorted(plain_imports)
    for module in sorted(from_imports):
        names = ", ".join(sorted(from_imports[module]))
        lines.append(f"from {module} import {names}")
    return lines


def read_version() -> str:
    init_source = (SRC / "__init__.py").read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_source)
    if not match:
        raise RuntimeError("could not find __version__ in src/wtime/__init__.py")
    return match.group(1)


def build() -> str:
    all_imports = []
    bodies = []
    for name in MODULE_ORDER:
        imports, body = split_module(SRC / name)
        all_imports.extend(imports)
        bodies.append(body)

    merged_imports = merge_imports(all_imports)
    version = read_version()

    parts = [HEADER]
    parts.append("\n".join(merged_imports))
    parts.append(f'\n__version__ = "{version}"\n')
    parts.append("\n\n\n".join(bodies))
    parts.append(FOOTER)
    return "\n".join(parts).rstrip("\n") + "\n"


def main() -> int:
    OUTPUT.write_text(build())
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
