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
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path


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

    # Default output
    if output is None:
        output = project_root / "dist" / "cde_editor.pyz"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # Copy entry point and HTML into flat archive layout
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
