#!/usr/bin/env python3
"""
Build the standalone CDE TSV Editor as a zipapp (.pyz).

The resulting archive can be distributed to curators who only need
Python 3.8+ installed — no pip packages required.

Usage:
    python scripts/build_editor_zipapp.py [--output PATH]

Output:
    dist/cde_editor.pyz  (default)
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path


def _read_cde_version(project_root: Path) -> str:
    """Read __version__ from cde_analyzer/__version__.py."""
    version_file = project_root / "cde_analyzer" / "__version__.py"
    if not version_file.exists():
        print(f"Warning: {version_file} not found, using fallback version",
              file=sys.stderr)
        return ""
    text = version_file.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else ""


def _read_fallback_version(main_py_text: str) -> str:
    """Extract the current _FALLBACK_VERSION from __main__.py source."""
    m = re.search(r'_FALLBACK_VERSION\s*=\s*"([^"]*)"', main_py_text)
    return m.group(1) if m else ""


def _stamp_version(main_py_text: str, version: str) -> tuple[str, str]:
    """Stamp _FALLBACK_VERSION in __main__.py if the base version differs.

    If the editor already has a more specific version (e.g., 0.8.1.3) that
    shares the same base as the codebase (0.8.1), the editor version is kept.
    Only overwrites when the base versions don't match.

    Returns (patched_text, version_used).
    """
    current = _read_fallback_version(main_py_text)
    # Keep editor version if it extends the codebase version (e.g., 0.8.1.3 extends 0.8.1)
    if current and current.startswith(version) and current != version:
        return main_py_text, current
    # Overwrite if base versions differ (e.g., 0.7.0 vs 0.8.1)
    patched = re.sub(
        r'_FALLBACK_VERSION\s*=\s*"[^"]*"',
        f'_FALLBACK_VERSION = "{version}"',
        main_py_text,
        count=1,
    )
    return patched, version


def build(output: Path | None = None) -> Path:
    """Assemble and create the zipapp archive."""
    project_root = Path(__file__).resolve().parent.parent

    # Source files
    main_py = project_root / "tools" / "editor_standalone" / "__main__.py"
    html_src = project_root / "actions" / "pattern_util" / "tsv_editor.html"

    for src in (main_py, html_src):
        if not src.exists():
            print(f"Error: source not found: {src}", file=sys.stderr)
            raise SystemExit(1)

    # Read cde_analyzer version for stamping
    cde_version = _read_cde_version(project_root)

    # Default output
    if output is None:
        output = project_root / "dist" / "cde_editor.pyz"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # Copy entry point — stamp version if available
        if cde_version:
            main_text = main_py.read_text(encoding="utf-8")
            main_text, used_version = _stamp_version(main_text, cde_version)
            (tmp_dir / "__main__.py").write_text(main_text, encoding="utf-8")
            print(f"  Version stamped: {used_version}")
        else:
            shutil.copy2(main_py, tmp_dir / "__main__.py")
        shutil.copy2(html_src, tmp_dir / "tsv_editor.html")

        # Create the zipapp
        zipapp.create_archive(
            source=tmp_dir,
            target=str(output),
            interpreter="/usr/bin/env python3",
        )

    size = output.stat().st_size
    print(f"Built: {output}")
    print(f"  Size: {size:,} bytes ({size / 1024:.1f} KB)")
    print(f"\nUsage:")
    print(f"  python {output.name} [FILE.tsv] [--port N] [--no-browser]")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build standalone CDE TSV Editor zipapp",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output path (default: dist/cde_editor.pyz)",
    )
    args = parser.parse_args()
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
