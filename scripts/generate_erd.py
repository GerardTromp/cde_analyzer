#!/usr/bin/env python3
"""
Generate an Entity-Relationship Diagram (ERD) from the CDE Pydantic models.

Uses erdantic to introspect the Pydantic model hierarchy and render
an SVG suitable for inclusion in scientific articles.

Requirements:
    pip install erdantic pydantic  (in the py313_erd venv)

Usage:
    python generate_erd.py [--output PATH] [--format FORMAT] [--root MODEL]

Venv:
    /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_erd
"""

import argparse
import sys
from pathlib import Path

# Ensure cde_analyzer package is importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Generate ERD from CDE Pydantic models"
    )
    parser.add_argument(
        "-o", "--output",
        default=str(project_root / "docs" / "diagrams" / "cde_erd.svg"),
        help="Output file path (default: docs/diagrams/cde_erd.svg)",
    )
    parser.add_argument(
        "-f", "--format",
        default=None,
        help="Output format (svg, png, pdf). Inferred from extension if omitted.",
    )
    parser.add_argument(
        "--root",
        default="CDEItem",
        choices=["CDEItem", "CDEForm", "both"],
        help="Root model(s) to diagram (default: CDEItem)",
    )
    args = parser.parse_args()

    import erdantic

    from CDE_Schema.CDE_Item import CDEItem
    from CDE_Schema.CDE_Form import CDEForm

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.root == "CDEItem":
        diagram = erdantic.create(CDEItem)
    elif args.root == "CDEForm":
        diagram = erdantic.create(CDEForm)
    else:  # both
        diagram = erdantic.create(CDEItem, CDEForm)

    diagram.draw(out_path)
    print(f"ERD written to {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"Models in diagram: {len(diagram.models)}")
    for model_key in sorted(diagram.models):
        print(f"  - {model_key}")


if __name__ == "__main__":
    main()
