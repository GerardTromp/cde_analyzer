#!/usr/bin/env python3
"""
Generate Health Drift: 180 noisy dose-tier copies of health base CDEs.

Reads the 60 health base CDEs and produces 180 noisy variants
(3 dose tiers × 60 originals).  Tests "drift" — how far each CDE
moves in embedding space when instrument/temporal noise is added,
and how drift varies with the verbosity tier of the source CDE.

Usage:
    python scripts/generate_health_drift.py \\
        --source data/synthetic_qc/health_base/health_base.json \\
        -o data/synthetic_qc/health_drift/health_drift.json --pretty

Noise tiers:
    Tier 1 (light)   _t1   Temporal phrase only
    Tier 2 (medium)  _t2   Instrument name only
    Tier 3 (heavy)   _t3   Temporal + instrument + extra anchor

Instruments:
    CMP   Clinical Monitoring Protocol       3 domain sub-scales
    HDQF  Health Data Quality Framework      Tier 3 only (extra anchor)

Uniform application: same temporal phrase and injection formula across
all 60 source CDEs.  The only varying factor is source verbosity:
    Cardiovascular (terse,  ~60-char defs)  → noise ≈ 100% → max drift
    Respiratory    (informational, ~200-char defs)  → moderate drift
    Metabolic      (expansive, ~450-char defs) → minimal drift
"""

import argparse
import copy
import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# Instrument definitions
# ---------------------------------------------------------------------------

CMP_PARENT = "Clinical Monitoring Protocol (CMP)"
CMP_SUBSCALES = {
    "Cardiovascular Assessment":        "CMP Cardiac Assessment",
    "Respiratory Function Evaluation":  "CMP Pulmonary Evaluation",
    "Metabolic Health Monitoring":      "CMP Metabolic Panel",
}

HDQF_PARENT = "Health Data Quality Framework (HDQF)"

TEMPORAL_PHRASE = "Over the past 30 days"
TEMPORAL_PHRASE_LOWER = "over the past 30 days"

# Domain tag → verbosity label (mirrors health base generator)
_VERBOSITY = {
    "Cardiovascular Assessment":        "terse",
    "Respiratory Function Evaluation":  "informational",
    "Metabolic Health Monitoring":      "expansive",
}

_DOMAIN_LABELS = {
    "Cardiovascular Assessment":        "cardiovascular",
    "Respiratory Function Evaluation":  "respiratory",
    "Metabolic Health Monitoring":      "metabolic",
}

# Base manifest data (mirrors generate_health_base.py manifest structure)
_MANIFEST_CRD = [
    ("Cardiac Parameters",  "cardiovascular"),
    ("Hemodynamics",        "xdh:blood_pressure"),
    ("Hemodynamics",        "cardiovascular"),
    ("Hemodynamics",        "cardiovascular"),
    ("Cardiac Parameters",  "cardiovascular"),
    ("Cardiac Parameters",  "cardiovascular"),
    ("Electrophysiology",   "cardiovascular"),
    ("Biomarkers",          "xdh:lab_values"),
    ("Biomarkers",          "cardiovascular"),
    ("Lipid Panel",         "cardiovascular"),
    ("Lipid Panel",         "cardiovascular"),
    ("Lipid Panel",         "cardiovascular"),
    ("Lipid Panel",         "cardiovascular"),
    ("Biomarkers",          "cardiovascular"),
    ("Vascular Imaging",    "xdh:imaging"),
    ("Electrophysiology",   "cardiovascular"),
    ("Anthropometry",       "xdh:bmi"),
    ("Medication",          "xdh:medication"),
    ("Demographics",        "xdh:demographics"),
    ("Treatment",           "xdh:treatment_response"),
]

_MANIFEST_RSP = [
    ("Spirometry",          "respiratory"),
    ("Spirometry",          "respiratory"),
    ("Spirometry",          "respiratory"),
    ("Spirometry",          "respiratory"),
    ("Oxygenation",         "respiratory"),
    ("Ventilation",         "respiratory"),
    ("Gas Exchange",        "respiratory"),
    ("Gas Exchange",        "xdh:lab_values"),
    ("Exercise Capacity",   "respiratory"),
    ("Gas Exchange",        "respiratory"),
    ("Ventilation",         "respiratory"),
    ("Spirometry",          "respiratory"),
    ("Symptoms",            "respiratory"),
    ("Biomarkers",          "respiratory"),
    ("Imaging",             "xdh:imaging"),
    ("Hemodynamics",        "xdh:blood_pressure"),
    ("Anthropometry",       "xdh:bmi"),
    ("Medication",          "xdh:medication"),
    ("Demographics",        "xdh:demographics"),
    ("Treatment",           "xdh:treatment_response"),
]

_MANIFEST_MET = [
    ("Glycemic",            "metabolic"),
    ("Glycemic",            "metabolic"),
    ("Glycemic",            "metabolic"),
    ("Glycemic",            "metabolic"),
    ("Anthropometry",       "metabolic"),
    ("Anthropometry",       "metabolic"),
    ("Lipid Panel",         "metabolic"),
    ("Lipid Panel",         "xdh:lab_values"),
    ("Renal/Metabolic",     "metabolic"),
    ("Hepatic",             "metabolic"),
    ("Hepatic",             "metabolic"),
    ("Renal/Metabolic",     "metabolic"),
    ("Renal/Metabolic",     "metabolic"),
    ("Endocrine",           "metabolic"),
    ("Imaging",             "xdh:imaging"),
    ("Hemodynamics",        "xdh:blood_pressure"),
    ("Anthropometry",       "xdh:bmi"),
    ("Medication",          "xdh:medication"),
    ("Demographics",        "xdh:demographics"),
    ("Treatment",           "xdh:treatment_response"),
]


# ---------------------------------------------------------------------------
# Noise injection functions
# ---------------------------------------------------------------------------

def _get_domain_tag(rec):
    """Extract the domain tag from a CDE record."""
    return rec["definitions"][0]["tags"][0]


def _get_cmp_subscale(domain_tag):
    """Get the CMP sub-scale for the given domain."""
    return CMP_SUBSCALES.get(domain_tag, "CMP General Assessment")


def inject_tier1(rec):
    """Tier 1 (light): temporal phrase only.

    - Designation 2 (question): prepend temporal phrase
    - Definition: append temporal clause
    """
    noisy = copy.deepcopy(rec)

    # Question: prepend temporal
    orig_q = noisy["designations"][1]["designation"]
    noisy["designations"][1]["designation"] = (
        f"{TEMPORAL_PHRASE}, {orig_q[0].lower()}{orig_q[1:]}"
    )

    # Definition: append temporal clause
    orig_d = noisy["definitions"][0]["definition"]
    if orig_d.endswith("."):
        orig_d = orig_d[:-1]
    noisy["definitions"][0]["definition"] = (
        f"{orig_d}, measured {TEMPORAL_PHRASE_LOWER}."
    )
    return noisy


def inject_tier2(rec):
    """Tier 2 (medium): instrument name only.

    - Designation 1 (name): prepend CMP sub-scale
    - Definition: append anchor phrase with CMP
    """
    noisy = copy.deepcopy(rec)
    domain_tag = _get_domain_tag(rec)
    subscale = _get_cmp_subscale(domain_tag)

    # Name: prepend instrument sub-scale
    orig_name = noisy["designations"][0]["designation"]
    noisy["designations"][0]["designation"] = f"{subscale} - {orig_name}"

    # Definition: append anchor phrase
    orig_d = noisy["definitions"][0]["definition"]
    noisy["definitions"][0]["definition"] = (
        f"{orig_d} A field of the {CMP_PARENT}."
    )
    return noisy


def inject_tier3(rec):
    """Tier 3 (heavy): temporal + instrument + extra anchor.

    Combines Tier 1 + Tier 2 + additional HDQF anchor.
    """
    noisy = copy.deepcopy(rec)
    domain_tag = _get_domain_tag(rec)
    subscale = _get_cmp_subscale(domain_tag)

    # Name: prepend instrument sub-scale (Tier 2)
    orig_name = noisy["designations"][0]["designation"]
    noisy["designations"][0]["designation"] = f"{subscale} - {orig_name}"

    # Question: prepend temporal (Tier 1)
    orig_q = noisy["designations"][1]["designation"]
    noisy["designations"][1]["designation"] = (
        f"{TEMPORAL_PHRASE}, {orig_q[0].lower()}{orig_q[1:]}"
    )

    # Definition: temporal clause + CMP anchor + HDQF anchor
    orig_d = noisy["definitions"][0]["definition"]
    if orig_d.endswith("."):
        orig_d = orig_d[:-1]
    noisy["definitions"][0]["definition"] = (
        f"{orig_d}, measured {TEMPORAL_PHRASE_LOWER}. "
        f"A field of the {CMP_PARENT}. "
        f"Based on the {HDQF_PARENT}."
    )
    return noisy


_TIER_FUNCS = {
    1: inject_tier1,
    2: inject_tier2,
    3: inject_tier3,
}

_TIER_LABELS = {
    1: "light",
    2: "medium",
    3: "heavy",
}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_noisy_copies(source_records):
    """Generate 180 noisy CDEs (3 tiers × 60 originals)."""
    records = []
    for tier in (1, 2, 3):
        inject_fn = _TIER_FUNCS[tier]
        for rec in source_records:
            noisy = inject_fn(rec)
            # Update tinyId with tier suffix
            noisy["tinyId"] = f"{rec['tinyId']}_t{tier}"
            records.append(noisy)
    return records


def generate_manifest(noisy_records, source_records):
    """Build manifest rows with noise metadata and source linkage."""
    # Build source manifest data lookup
    manifest_data = _MANIFEST_CRD + _MANIFEST_RSP + _MANIFEST_MET
    source_meta = {}
    for rec, (sub_domain, expected_cluster) in zip(source_records, manifest_data):
        domain_tag = _get_domain_tag(rec)
        source_meta[rec["tinyId"]] = {
            "domain": _DOMAIN_LABELS[domain_tag],
            "domain_full": domain_tag,
            "sub_domain": sub_domain,
            "verbosity": _VERBOSITY[domain_tag],
            "expected_cluster": expected_cluster,
            "name": rec["designations"][0]["designation"],
        }

    rows = []
    for rec in noisy_records:
        tiny_id = rec["tinyId"]
        # Extract source tinyId and tier from "synCRD001_t1" format
        source_id = tiny_id.rsplit("_t", 1)[0]
        tier = int(tiny_id.rsplit("_t", 1)[1])

        meta = source_meta[source_id]
        domain_tag = meta["domain_full"]
        subscale = _get_cmp_subscale(domain_tag)

        # Determine noise components
        if tier == 1:
            instrument = ""
            temporal = TEMPORAL_PHRASE
            anchor = ""
        elif tier == 2:
            instrument = subscale
            temporal = ""
            anchor = ""
        else:  # tier 3
            instrument = subscale
            temporal = TEMPORAL_PHRASE
            anchor = HDQF_PARENT

        rows.append({
            "tinyId": tiny_id,
            "domain": meta["domain"],
            "domain_full": meta["domain_full"],
            "sub_domain": meta["sub_domain"],
            "verbosity": meta["verbosity"],
            "expected_cluster": meta["expected_cluster"],
            "name": meta["name"],
            "noise_tier": _TIER_LABELS[tier],
            "instrument": instrument,
            "temporal_phrase": temporal,
            "anchor_phrase": anchor,
            "source_tinyId": source_id,
        })
    return rows


def write_manifest_tsv(rows, path):
    fields = [
        "tinyId", "domain", "domain_full", "sub_domain",
        "verbosity", "expected_cluster", "name",
        "noise_tier", "instrument", "temporal_phrase",
        "anchor_phrase", "source_tinyId",
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate Health Drift: 180 noisy dose-tier copies of "
                    "health base CDEs for drift analysis."
    )
    parser.add_argument("--source", "-s", required=True,
                        help="Source JSON file (health base CDEs)")
    parser.add_argument("-o", "--output", required=True,
                        help="Output JSON file path")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON (indented)")
    parser.add_argument("--manifest", default=None,
                        help="Output manifest TSV path")
    args = parser.parse_args()

    # Load source CDEs
    with open(args.source, "r", encoding="utf-8") as f:
        source_records = json.load(f)

    print(f"Loaded {len(source_records)} source CDEs from {args.source}")

    # Ensure output directory exists
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Generate noisy copies
    noisy_records = generate_noisy_copies(source_records)

    # Write CDE JSON
    indent = 2 if args.pretty else None
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        json.dump(noisy_records, f, indent=indent, ensure_ascii=False)
        f.write("\n")

    # Write manifest TSV
    manifest_path = args.manifest
    if manifest_path is None:
        base = os.path.splitext(os.path.basename(args.output))[0]
        manifest_path = os.path.join(out_dir or ".", f"{base}_manifest.tsv")
    manifest_rows = generate_manifest(noisy_records, source_records)
    write_manifest_tsv(manifest_rows, manifest_path)

    # Summary
    print(f"Generated {len(noisy_records)} health-drift CDEs → {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) → {manifest_path}")

    # Tier × verbosity breakdown
    tier_verb = {}
    for row in manifest_rows:
        key = (row["noise_tier"], row["verbosity"])
        tier_verb[key] = tier_verb.get(key, 0) + 1

    print("\nTier × Verbosity breakdown:")
    for (tier, verb), count in sorted(tier_verb.items()):
        print(f"  {tier:8s} × {verb:14s}: {count} CDEs")

    # Noise injection stats
    for tier_label in ("light", "medium", "heavy"):
        tier_rows = [r for r in manifest_rows if r["noise_tier"] == tier_label]
        has_inst = sum(1 for r in tier_rows if r["instrument"])
        has_temp = sum(1 for r in tier_rows if r["temporal_phrase"])
        has_anchor = sum(1 for r in tier_rows if r["anchor_phrase"])
        print(f"\n  {tier_label}: {len(tier_rows)} CDEs — "
              f"instrument: {has_inst}, temporal: {has_temp}, "
              f"anchor: {has_anchor}")

    # Sample: show one CDE per tier for the first source CDE
    first_source = source_records[0]["tinyId"]
    print(f"\nSample injection for {first_source}:")
    for tier in (1, 2, 3):
        tid = f"{first_source}_t{tier}"
        rec = next(r for r in noisy_records if r["tinyId"] == tid)
        name = rec["designations"][0]["designation"]
        question = rec["designations"][1]["designation"]
        defn = rec["definitions"][0]["definition"]
        print(f"\n  Tier {tier} ({_TIER_LABELS[tier]}):")
        print(f"    Name:  {name}")
        print(f"    Q:     {question[:80]}...")
        print(f"    Def:   {defn[:100]}...")


if __name__ == "__main__":
    main()
