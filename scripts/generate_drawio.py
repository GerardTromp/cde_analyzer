#!/usr/bin/env python3
"""
Generate draw.io (.drawio) ERD files from CDE Pydantic models.

Produces editable draw.io diagrams with:
- Proper ERD entity shapes with field rows
- Colour-coded headers by role
- Relationship edges with cardinality notation
- Two layers: "Entities" and "Relationships" for easy toggling

Usage:
    python generate_drawio.py [--mode core|full|both]

Outputs:
    docs/diagrams/cde_core_erd.drawio   — publication figure (6 models)
    docs/diagrams/cde_full_erd.drawio   — appendix/supplement (41 models)
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import get_args, get_origin

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# ── Colour palette ─────────────────────────────────────────────────

ROLE_COLOURS = {
    # (header_bg, header_fg, row_bg)
    "root":       ("#1a73e8", "#ffffff", "#e8f0fe"),
    "text":       ("#e8a817", "#ffffff", "#fef7e0"),
    "value":      ("#1e8e3e", "#ffffff", "#e6f4ea"),
    "enum":       ("#c5221f", "#ffffff", "#fce8e6"),
    "identifier": ("#7627bb", "#ffffff", "#f3e8fd"),
    "metadata":   ("#5f6368", "#ffffff", "#f1f3f4"),
    "default":    ("#666666", "#ffffff", "#f5f5f5"),
}

# Role assignment for core models
CORE_ROLES = {
    "CDEItem": "root",
    "Designation": "text",
    "Definition": "text",
    "ValueDomain": "value",
    "PermissibleValue": "enum",
    "Identifier": "identifier",
}

# Role assignment for full model (core roles + everything else)
FULL_ROLES = {
    **CORE_ROLES,
    "CDEForm": "root",
    "Source": "metadata",
    "CreatedBy": "metadata",
    "UpdatedBy": "metadata",
    "StewardOrg": "metadata",
    "RegistrationState": "metadata",
    "Classification": "metadata",
    "ReferenceDocument": "metadata",
    "Property": "metadata",
    "Comment": "metadata",
    "Attachment": "metadata",
    "DataSet": "metadata",
    "DerivationRule": "metadata",
    "Tag": "metadata",
    "Copyright": "metadata",
    "FormCopyright": "metadata",
    "DisplayProfile": "metadata",
}

# ── Pydantic introspection ─────────────────────────────────────────

def _resolve_inner_type(annotation):
    """Unwrap Optional[X], List[X] to get base model class name."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    import types

    if annotation is type(None):
        return None
    if origin is types.UnionType or str(origin) == "typing.Union":
        for a in args:
            if a is not type(None):
                return _resolve_inner_type(a)
    if origin is list:
        return _resolve_inner_type(args[0]) if args else None
    if isinstance(annotation, type):
        return annotation.__name__
    return getattr(annotation, '__name__', None)


def _type_display(annotation) -> str:
    """Short human-readable type string."""
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
            return _type_display(non_none[0]) + "?"
        return " | ".join(_type_display(a) for a in non_none)
    if origin is list:
        return f"List[{_type_display(args[0])}]" if args else "List"
    return str(annotation).replace("typing.", "")


def _is_list_type(annotation) -> bool:
    """Check if the resolved type is a List."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    import types

    if origin is list:
        return True
    if origin is types.UnionType or str(origin) == "typing.Union":
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _is_list_type(non_none[0])
    return False


def introspect_model(model_cls, included_models):
    """Return (fields, edges) for a model within the included set."""
    fields = []
    edges = []

    for name, field_info in model_cls.model_fields.items():
        ann = field_info.annotation
        inner = _resolve_inner_type(ann)
        type_str = _type_display(ann)
        is_ref = inner in included_models if inner else False
        fields.append((name, type_str, is_ref))

        if is_ref:
            card = "1..*" if _is_list_type(ann) else "0..1"
            edges.append((name, inner, card))

    return fields, edges


# ── draw.io XML generation ─────────────────────────────────────────

def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _entity_style(header_bg, row_bg):
    """Style for the container entity cell."""
    return (
        f"shape=table;startSize=30;container=1;collapsible=1;"
        f"childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;"
        f"align=center;resizeLast=1;fontSize=13;fontFamily=Helvetica;"
        f"fillColor={header_bg};fontColor=#ffffff;strokeColor=#333333;"
        f"rounded=1;arcSize=8;shadow=1;"
    )


def _row_style(row_bg, is_ref=False):
    """Style for a field row cell."""
    font_style = "1" if is_ref else "0"
    return (
        f"shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;"
        f"swimlaneBody=0;fillColor={row_bg};collapsible=0;dropTarget=0;"
        f"points=[[0,0.5],[1,0.5]];portConstraint=eastwest;fontSize=11;"
        f"fontStyle={font_style};fontFamily=Helvetica;strokeColor=#dddddd;"
    )


def _field_cell_style(align="left", is_type=False):
    """Style for individual field name/type cells within a row."""
    colour = "#888888" if is_type else "#333333"
    return (
        f"shape=partialRectangle;connectable=0;fillColor=none;"
        f"top=0;left=0;bottom=0;right=0;fontStyle=0;overflow=hidden;"
        f"fontSize=11;fontFamily=Helvetica;fontColor={colour};align={align};"
    )


def _edge_style(card):
    """Edge style with ERD cardinality markers."""
    if card == "1..*":
        return (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
            "jettySize=auto;html=1;exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
            "endArrow=ERmany;endFill=0;startArrow=ERmandOne;startFill=0;"
            "strokeColor=#555555;fontSize=10;fontFamily=Helvetica;"
            "curved=1;"
        )
    else:  # 0..1 or 1
        return (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
            "jettySize=auto;html=1;exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
            "endArrow=ERzeroToOne;endFill=0;startArrow=ERmandOne;startFill=0;"
            "strokeColor=#555555;fontSize=10;fontFamily=Helvetica;"
            "curved=1;"
        )


# ── Layout ─────────────────────────────────────────────────────────

# Predefined positions for the core diagram (hand-tuned for readability)
CORE_LAYOUT = {
    "CDEItem":          (300, 40),
    "Designation":      (40,  620),
    "Definition":       (300, 620),
    "ValueDomain":      (560, 620),
    "Identifier":       (100, 1100),
    "PermissibleValue": (500, 1100),
}


def _auto_layout(model_names):
    """Grid layout for full model — 4 columns."""
    cols = 4
    col_w, row_h = 320, 500
    margin_x, margin_y = 40, 40
    positions = {}
    for i, name in enumerate(sorted(model_names)):
        c = i % cols
        r = i // cols
        positions[name] = (margin_x + c * col_w, margin_y + r * row_h)
    return positions


# ── Build drawio XML ───────────────────────────────────────────────

def build_drawio(models_map, roles, layout, title="CDE ERD"):
    """Build a complete .drawio XML string."""
    included = set(models_map.keys())

    # Root structure
    mxfile = ET.Element("mxfile", host="app.diagrams.net", type="device")
    diagram = ET.SubElement(mxfile, "diagram", name=title, id="erd-page-1")
    graph_model = ET.SubElement(diagram, "mxGraphModel",
                                dx="1200", dy="800", grid="1", gridSize="10",
                                guides="1", tooltips="1", connect="1",
                                arrows="1", fold="1", page="1",
                                pageScale="1", pageWidth="1600", pageHeight="2400")
    root = ET.SubElement(graph_model, "root")

    # Layer 0 (default parent)
    ET.SubElement(root, "mxCell", id="0")
    # Layer 1 — Entities
    ET.SubElement(root, "mxCell", id="layer-entities", value="Entities",
                  style="locked=0;", parent="0")
    # Layer 2 — Relationships
    ET.SubElement(root, "mxCell", id="layer-rels", value="Relationships",
                  style="locked=0;", parent="0")

    cell_id = 100
    # Map: model_name -> entity_cell_id
    entity_ids = {}
    # Map: (model_name, field_name) -> row_cell_id (for edge source)
    row_ids = {}

    ROW_H = 28
    ENTITY_W = 260

    for model_name, model_cls in sorted(models_map.items()):
        role = roles.get(model_name, "default")
        hdr_bg, hdr_fg, row_bg = ROLE_COLOURS.get(role, ROLE_COLOURS["default"])

        fields, edges = introspect_model(model_cls, included)
        edge_field_names = {e[0] for e in edges}

        x, y = layout.get(model_name, (40, 40))
        entity_h = 30 + len(fields) * ROW_H

        # Entity container
        eid = str(cell_id); cell_id += 1
        entity_ids[model_name] = eid
        ET.SubElement(root, "mxCell", id=eid, value=model_name,
                      style=_entity_style(hdr_bg, row_bg),
                      vertex="1", parent="layer-entities")
        geo = ET.SubElement(root[-1], "mxGeometry",
                            x=str(x), y=str(y),
                            width=str(ENTITY_W), height=str(entity_h))
        geo.set("as", "geometry")

        # Field rows
        for fname, ftype, is_ref in fields:
            row_id = str(cell_id); cell_id += 1
            ref_in_edge = fname in edge_field_names

            ET.SubElement(root, "mxCell", id=row_id, value="",
                          style=_row_style(row_bg, ref_in_edge),
                          vertex="1", parent=eid)
            rg = ET.SubElement(root[-1], "mxGeometry",
                               width=str(ENTITY_W), height=str(ROW_H))
            rg.set("as", "geometry")

            row_ids[(model_name, fname)] = row_id

            # Field name cell
            fn_id = str(cell_id); cell_id += 1
            ET.SubElement(root, "mxCell", id=fn_id,
                          value=_xml_escape(fname),
                          style=_field_cell_style("left", is_type=False),
                          vertex="1", connectable="0", parent=row_id)
            fg = ET.SubElement(root[-1], "mxGeometry",
                               width=str(ENTITY_W // 2), height=str(ROW_H))
            fg.set("as", "geometry")

            # Type cell
            ft_id = str(cell_id); cell_id += 1
            ET.SubElement(root, "mxCell", id=ft_id,
                          value=_xml_escape(ftype),
                          style=_field_cell_style("left", is_type=True),
                          vertex="1", connectable="0", parent=row_id)
            tg = ET.SubElement(root[-1], "mxGeometry",
                               x=str(ENTITY_W // 2),
                               width=str(ENTITY_W // 2), height=str(ROW_H))
            tg.set("as", "geometry")

    # Edges
    for model_name, model_cls in sorted(models_map.items()):
        fields, edges = introspect_model(model_cls, included)
        for fname, target, card in edges:
            src_row = row_ids.get((model_name, fname))
            tgt_entity = entity_ids.get(target)
            if src_row and tgt_entity:
                eid = str(cell_id); cell_id += 1
                ET.SubElement(root, "mxCell", id=eid, value=card,
                              style=_edge_style(card),
                              edge="1", parent="layer-rels",
                              source=src_row, target=tgt_entity)
                eg = ET.SubElement(root[-1], "mxGeometry", relative="1")
                eg.set("as", "geometry")

    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


# ── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate draw.io ERD files")
    parser.add_argument("--mode", choices=["core", "full", "both"],
                        default="both", help="Which diagram(s) to generate")
    args = parser.parse_args()

    out_dir = project_root / "docs" / "diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode in ("core", "both"):
        from CDE_Schema.CDE_Item import CDEItem
        from CDE_Schema.classes import (
            Designation, Definition, ValueDomain,
            PermissibleValue, Identifier,
        )
        core_models = {
            "CDEItem": CDEItem,
            "Designation": Designation,
            "Definition": Definition,
            "ValueDomain": ValueDomain,
            "PermissibleValue": PermissibleValue,
            "Identifier": Identifier,
        }
        xml = build_drawio(core_models, CORE_ROLES, CORE_LAYOUT,
                           title="CDE Core Data Model")
        path = out_dir / "cde_core_erd.drawio"
        path.write_text(xml, encoding="utf-8")
        print(f"Core:  {path} ({path.stat().st_size:,} bytes, "
              f"{len(core_models)} models)")

    if args.mode in ("full", "both"):
        from CDE_Schema.CDE_Item import CDEItem
        from CDE_Schema.CDE_Form import CDEForm
        from CDE_Schema import classes as cls

        # Collect all BaseModel subclasses from classes.py + CDEItem/CDEForm
        import inspect
        from pydantic import BaseModel
        full_models = {}
        for name, obj in inspect.getmembers(cls, inspect.isclass):
            if issubclass(obj, BaseModel) and obj is not BaseModel:
                full_models[name] = obj
        full_models["CDEItem"] = CDEItem
        full_models["CDEForm"] = CDEForm

        layout = _auto_layout(full_models.keys())
        xml = build_drawio(full_models, FULL_ROLES, layout,
                           title="CDE Full Data Model")
        path = out_dir / "cde_full_erd.drawio"
        path.write_text(xml, encoding="utf-8")
        print(f"Full:  {path} ({path.stat().st_size:,} bytes, "
              f"{len(full_models)} models)")


if __name__ == "__main__":
    main()
