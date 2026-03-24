"""
Shared utilities for synthetic CDE generators.

Consolidates boilerplate, CDE record building, injection logic,
manifest writing, CLI scaffolding, and reporting that was duplicated
across 6+ generator scripts.
"""

import argparse
import csv
import json
import os

# ---------------------------------------------------------------------------
# CDE record building
# ---------------------------------------------------------------------------

_BOILERPLATE = {
    "nihEndorsed": None,
    "elementType": "cde",
    "archived": False,
    "sources": [],
    "createdBy": None,
    "stewardOrg": {"name": "Synthetic QC"},
    "registrationState": {"registrationStatus": "Qualified"},
    "classification": [],
    "referenceDocuments": [],
    "properties": [],
    "ids": [],
    "attachments": [],
}


def make_tiny_id(prefix: str, index: int) -> str:
    """Generate a deterministic synthetic tinyId."""
    return f"syn{prefix}{index:03d}"


def build_record(tiny_id, name, question, definition, topic_tag):
    """Build a single CDE JSON record with the standard structure."""
    rec = dict(_BOILERPLATE)
    rec["tinyId"] = tiny_id
    rec["designations"] = [
        {"designation": name, "sources": None, "tags": [topic_tag]},
        {"designation": question, "sources": None, "tags": [topic_tag]},
    ]
    rec["definitions"] = [
        {"definition": definition, "sources": None, "tags": [topic_tag]},
    ]
    return rec


# ---------------------------------------------------------------------------
# Injection engine
# ---------------------------------------------------------------------------

def inject_gravity(index, name, question, definition, topic_key,
                   family1_subscales, family1_parent,
                   family2_subscales, family2_parent,
                   temporals):
    """Apply gravity-style instrument/temporal injection.

    Standard 20-CDE-per-topic layout:
        0-5:   Family 1 full injection (name + question + definition)
        6-11:  Family 2 full injection
        12-14: Family 1 definition-only (weak gravity)
        15-16: Temporal only
        17-19: Clean controls

    Returns (name, question, definition, instrument_name, temporal_phrase).
    """
    instrument = ""
    temporal = ""

    if index <= 5:
        subscale = family1_subscales[topic_key]
        instrument = subscale
        temporal = temporals[index % len(temporals)]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} As part of the {family1_parent}."
    elif index <= 11:
        subscale = family2_subscales[topic_key]
        instrument = subscale
        temporal = temporals[index % len(temporals)]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} Based on the {family2_parent}."
    elif index <= 14:
        instrument = family1_subscales[topic_key]
        definition = f"{definition} A field of the {family1_parent}."
    elif index <= 16:
        temporal = temporals[index % len(temporals)]
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        # Append temporal clause to definition
        if definition.endswith("."):
            definition = definition[:-1]
        definition = f"{definition}, assessed {temporal.lower()}."
    # 17-19: clean — no modification

    return name, question, definition, instrument, temporal


def injection_site_label(index):
    """Return the injection site label for a given within-topic index."""
    if index <= 11:
        return "name+question+definition"
    elif index <= 14:
        return "definition_only"
    elif index <= 16:
        return "temporal_only"
    else:
        return "clean"


def inject_drift_tier1(question, definition, temporal, temporal_clause):
    """Tier 1 drift: temporal in question + temporal clause in definition."""
    question = f"{temporal}, {question[0].lower()}{question[1:]}"
    definition = f"{definition} {temporal_clause}"
    return question, definition


def inject_drift_tier2(name, definition, subscale, anchor):
    """Tier 2 drift: instrument in name + anchor in definition."""
    name = f"{subscale} - {name}"
    definition = f"{definition} {anchor}"
    return name, definition


def inject_drift_tier3(name, question, definition, subscale, temporal,
                       anchor, temporal_clause):
    """Tier 3 drift: combined instrument + temporal + extra anchor."""
    name = f"{subscale} - {name}"
    question = f"{temporal}, {question[0].lower()}{question[1:]}"
    definition = f"{definition} {anchor} {temporal_clause}"
    return name, question, definition


# ---------------------------------------------------------------------------
# Manifest building
# ---------------------------------------------------------------------------

_MANIFEST_FIELDS = [
    "tinyId", "domain", "domain_full", "sub_domain",
    "verbosity", "expected_cluster", "name",
    "instrument", "temporal_phrase", "injection_site",
]


def build_manifest_row(rec, base_name, sub_domain, expected_cluster,
                       domain_label, verbosity, instrument, temporal,
                       injection_site, extra_fields=None):
    """Build a single manifest row dict."""
    row = {
        "tinyId": rec["tinyId"],
        "domain": domain_label,
        "domain_full": rec["definitions"][0]["tags"][0],
        "sub_domain": sub_domain,
        "verbosity": verbosity,
        "expected_cluster": expected_cluster,
        "name": base_name,
        "instrument": instrument,
        "temporal_phrase": temporal,
        "injection_site": injection_site,
    }
    if extra_fields:
        row.update(extra_fields)
    return row


def write_manifest_tsv(rows, path, fields=None):
    """Write manifest rows to a TSV file."""
    if fields is None:
        fields = _MANIFEST_FIELDS
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t",
                                lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI scaffolding
# ---------------------------------------------------------------------------

def make_parser(description, extra_args=None):
    """Create standard argparse parser with output/pretty/manifest flags."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-o", "--output", required=True,
                        help="Output JSON file path")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON (indented)")
    parser.add_argument("--manifest", default=None,
                        help="Output manifest TSV path")
    if extra_args:
        for args, kwargs in extra_args:
            parser.add_argument(*args, **kwargs)
    return parser


def ensure_output_dir(output_path):
    """Ensure the parent directory of output_path exists. Returns dir path."""
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    return out_dir or "."


def write_cde_json(records, path, pretty=False):
    """Write CDE records to JSON file."""
    indent = 2 if pretty else None
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(records, f, indent=indent, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_summary(records, manifest_rows, topics, verbosity_map):
    """Print standard generation summary."""
    print(f"Generated {len(records)} synthetic CDEs")
    print(f"Manifest: {len(manifest_rows)} rows")

    for prefix, topic, tag, *_ in topics:
        avg_def = sum(len(d) for _, _, d in topic) / len(topic)
        avg_name = sum(len(n) for n, _, _ in topic) / len(topic)
        verbosity = verbosity_map.get(tag, "unknown")
        print(f"  {tag} ({verbosity}): avg name {avg_name:.0f} chars, "
              f"avg def {avg_def:.0f} chars")


def report_injection_distribution(manifest_rows):
    """Print instrument and temporal injection distribution."""
    inst_counts = {}
    temporal_counts = {}
    for row in manifest_rows:
        if row.get("instrument"):
            inst_counts[row["instrument"]] = \
                inst_counts.get(row["instrument"], 0) + 1
        if row.get("temporal_phrase"):
            temporal_counts[row["temporal_phrase"]] = \
                temporal_counts.get(row["temporal_phrase"], 0) + 1

    print(f"\nInstrument injection: {sum(inst_counts.values())} CDEs")
    for inst, count in sorted(inst_counts.items()):
        print(f"  {inst}: {count}")

    print(f"\nTemporal injection: {sum(temporal_counts.values())} CDEs")
    for tmp, count in sorted(temporal_counts.items()):
        print(f"  {tmp}: {count}")


def report_cross_domain(manifest_rows, prefix="xd"):
    """Print cross-domain group summary."""
    xd_counts = {}
    for row in manifest_rows:
        cl = row["expected_cluster"]
        if cl.startswith(prefix):
            xd_counts.setdefault(cl, []).append(row["tinyId"])
    print(f"\nCross-domain overlap: {len(xd_counts)} groups, "
          f"{sum(len(v) for v in xd_counts.values())} CDEs")
    for cl, ids in sorted(xd_counts.items()):
        print(f"  {cl}: {', '.join(ids)}")
