#!/usr/bin/env python3
"""
Generate a focused ERD showing the CDEItem core data chain.

Introspects the real Pydantic models but renders only the selected
subset: CDEItem → Designation/Definition/ValueDomain → PermissibleValue.

Produces a publication-quality SVG via Graphviz DOT.

Usage:
    python generate_erd_focused.py [-o PATH]
"""

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import get_args, get_origin

# Ensure cde_analyzer package is importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# ── Configuration ──────────────────────────────────────────────────
# Models to include and the edges to draw between them.
# Only fields pointing to INCLUDED models generate edges.
INCLUDE_MODELS = {
    "CDEItem",
    "Designation",
    "Definition",
    "ValueDomain",
    "PermissibleValue",
    "Identifier",
}

# ── Introspection helpers ──────────────────────────────────────────

def _resolve_inner_type(annotation):
    """Unwrap Optional[X], List[X], etc. to get the base model name."""
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[X] is Union[X, None]
    if origin is type(None):
        return None

    # Handle Union (Optional)
    import types
    if origin is types.UnionType or (hasattr(origin, '__name__') and origin.__name__ == 'Union'):
        for a in args:
            if a is type(None):
                continue
            return _resolve_inner_type(a)

    # Handle List[X]
    if origin is list:
        if args:
            return _resolve_inner_type(args[0])
        return None

    # Handle bare type references
    if isinstance(annotation, type):
        return annotation.__name__

    # Try __name__ for other cases
    name = getattr(annotation, '__name__', None)
    if name:
        return name

    return None


def _python_type_name(annotation) -> str:
    """Human-readable type string for a field annotation."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    import types

    if annotation is type(None):
        return "None"

    if isinstance(annotation, type):
        return annotation.__name__

    if origin is types.UnionType or str(origin) == "typing.Union":
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            # Optional[X]
            return f"{_python_type_name(non_none[0])}?"
        return " | ".join(_python_type_name(a) for a in non_none)

    if origin is list:
        if args:
            return f"List[{_python_type_name(args[0])}]"
        return "List"

    return str(annotation).replace("typing.", "")


def introspect_model(model_cls):
    """Extract fields and relationships from a Pydantic model."""
    fields = []
    edges = []

    for name, field_info in model_cls.model_fields.items():
        annotation = field_info.annotation
        inner = _resolve_inner_type(annotation)
        type_str = _python_type_name(annotation)

        # Determine cardinality
        origin = get_origin(annotation)
        args = get_args(annotation)
        import types

        # Unwrap Optional first
        actual_type = annotation
        if origin is types.UnionType or str(origin) == "typing.Union":
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                actual_type = non_none[0]

        actual_origin = get_origin(actual_type)
        is_list = actual_origin is list

        if inner and inner in INCLUDE_MODELS:
            cardinality = "1..*" if is_list else "1"
            edges.append((name, inner, cardinality))

        fields.append((name, type_str, inner in INCLUDE_MODELS if inner else False))

    return fields, edges


# ── DOT generation ─────────────────────────────────────────────────

DOT_HEADER = textwrap.dedent("""\
    digraph CDE_Core_Schema {
        graph [
            rankdir=TB
            fontname="Helvetica"
            fontsize=11
            label="CDE Core Data Model"
            labelloc=t
            pad=0.4
            nodesep=0.6
            ranksep=1.0
            bgcolor=white
        ];
        node [
            shape=none
            fontname="Helvetica"
            fontsize=10
        ];
        edge [
            fontname="Helvetica"
            fontsize=9
            color="#555555"
            arrowsize=0.8
        ];
""")

# Colour palette — muted tones suitable for print
COLOURS = {
    "CDEItem":          ("#e8f0fe", "#1a73e8"),   # blue — root
    "Designation":      ("#fef7e0", "#e8a817"),   # amber — text fields
    "Definition":       ("#fef7e0", "#e8a817"),
    "ValueDomain":      ("#e6f4ea", "#1e8e3e"),   # green — value typing
    "PermissibleValue": ("#fce8e6", "#c5221f"),   # red — enumerated values
    "Identifier":       ("#f3e8fd", "#7627bb"),   # purple — identifiers
}
DEFAULT_COLOUR = ("#f5f5f5", "#444444")


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _model_node(name, fields, edges_set):
    """Generate an HTML-label table node for a model."""
    fill, accent = COLOURS.get(name, DEFAULT_COLOUR)
    edge_field_names = {e[0] for e in edges_set}

    rows = []
    for fname, ftype, is_ref in fields:
        ftype_esc = _html_escape(ftype)
        if fname in edge_field_names:
            # Relationship field — bold + accent colour
            rows.append(
                f'<TR><TD ALIGN="LEFT" PORT="{fname}">'
                f'<B><FONT COLOR="{accent}">{fname}</FONT></B></TD>'
                f'<TD ALIGN="LEFT"><FONT COLOR="{accent}">{ftype_esc}</FONT></TD></TR>'
            )
        else:
            rows.append(
                f'<TR><TD ALIGN="LEFT">{fname}</TD>'
                f'<TD ALIGN="LEFT"><FONT COLOR="#888888">{ftype_esc}</FONT></TD></TR>'
            )

    field_rows = "\n            ".join(rows)
    return textwrap.dedent(f"""\
        {name} [label=<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6">
            <TR><TD COLSPAN="2" BGCOLOR="{accent}"><B><FONT COLOR="white" POINT-SIZE="12">{name}</FONT></B></TD></TR>
            {field_rows}
        </TABLE>>];
    """)


def _edge_line(src_model, field_name, tgt_model, cardinality):
    """Generate a DOT edge with cardinality label."""
    style = 'style=dashed' if cardinality == "1" else ''
    head = "crowodot" if cardinality == "1..*" else "vee"
    return (
        f'    {src_model}:{field_name} -> {tgt_model} '
        f'[arrowhead={head} {style} label="  {cardinality}  "];'
    )


def generate_dot(models_map):
    """Build the complete DOT source."""
    lines = [DOT_HEADER]

    all_edges = []
    for model_name in INCLUDE_MODELS:
        if model_name not in models_map:
            continue
        model_cls = models_map[model_name]
        fields, edges = introspect_model(model_cls)
        lines.append(_model_node(model_name, fields, edges))
        for field_name, target, cardinality in edges:
            all_edges.append((model_name, field_name, target, cardinality))

    lines.append("    // Relationships")
    for src, fname, tgt, card in all_edges:
        lines.append(_edge_line(src, fname, tgt, card))

    lines.append("}")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate focused CDE core-chain ERD"
    )
    parser.add_argument(
        "-o", "--output",
        default=str(project_root / "docs" / "diagrams" / "cde_core_erd.svg"),
        help="Output SVG path (default: docs/diagrams/cde_core_erd.svg)",
    )
    args = parser.parse_args()

    # Import models
    from CDE_Schema.CDE_Item import CDEItem
    from CDE_Schema.classes import (
        Designation, Definition, ValueDomain,
        PermissibleValue, Identifier,
    )

    models_map = {
        "CDEItem": CDEItem,
        "Designation": Designation,
        "Definition": Definition,
        "ValueDomain": ValueDomain,
        "PermissibleValue": PermissibleValue,
        "Identifier": Identifier,
    }

    dot_source = generate_dot(models_map)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dot_file = out_path.with_suffix(".dot")
    dot_file.write_text(dot_source, encoding="utf-8")

    # Render SVG
    result = subprocess.run(
        ["dot", "-Tsvg", "-o", str(out_path), str(dot_file)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Graphviz error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"DOT source:  {dot_file}")
    print(f"SVG written: {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"Models: {', '.join(sorted(models_map.keys()))}")


if __name__ == "__main__":
    main()
