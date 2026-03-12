#!/usr/bin/env python3
"""
Generate Health Neuro Drift: 180 noisy dose-tier copies of health neuro CDEs.

Reads the 60 health neuro CDEs and produces 180 noisy variants
(3 dose tiers x 60 originals).  Tests "drift" -- how far each CDE
moves in embedding space when instrument/temporal noise is added,
and how drift interacts with the verbosity tier of the source CDE.

Unlike health_drift (where verbosity is confounded with domain),
health_neuro_drift holds the domain CONSTANT (neurology) and varies
verbosity within each concept.  This isolates the verbosity x noise
interaction.

Usage:
    python scripts/generate_health_neuro_drift.py \\
        --source data/synthetic_qc/health_neuro/health_neuro.json \\
        -o data/synthetic_qc/health_neuro_drift/health_neuro_drift.json --pretty

Noise tiers:
    Tier 1 (light)   _t1   Temporal phrase only
    Tier 2 (medium)  _t2   Instrument name only
    Tier 3 (heavy)   _t3   Temporal + instrument + extra anchor

Instruments:
    NESS   Neurological Examination Standardized Scale   5 sub-modules
    NCRF   Neurology Clinical Research Framework         Tier 3 only (anchor)

Sub-module assignment by sub-domain:
    Cerebrovascular   -> NESS Cerebrovascular Module
    Epilepsy          -> NESS Seizure Module
    Movement Disorders -> NESS Motor Function Module
    Headache          -> NESS Cephalgia Module
    Neuropathy        -> NESS Peripheral Nerve Module
"""

import argparse
import copy
import csv
import json
import os

# ---------------------------------------------------------------------------
# Instrument definitions
# ---------------------------------------------------------------------------

NESS_PARENT = "Neurological Examination Standardized Scale (NESS)"
NESS_SUBMODULES = {
    "Cerebrovascular":     "NESS Cerebrovascular Module",
    "Epilepsy":            "NESS Seizure Module",
    "Movement Disorders":  "NESS Motor Function Module",
    "Headache":            "NESS Cephalgia Module",
    "Neuropathy":          "NESS Peripheral Nerve Module",
}

NCRF_PARENT = "Neurology Clinical Research Framework (NCRF)"

TEMPORAL_PHRASE = "During the past 6 months"
TEMPORAL_PHRASE_LOWER = "during the past 6 months"

# Concept metadata from generate_health_neuro.py
_TIER_SUFFIX = {"T": "terse", "I": "informational", "E": "expansive"}

# Sub-domain lookup by concept number (1-based)
_CONCEPT_SUBDOMAIN = {
    1: "Cerebrovascular", 2: "Cerebrovascular",
    3: "Cerebrovascular", 4: "Cerebrovascular",
    5: "Epilepsy", 6: "Epilepsy",
    7: "Epilepsy", 8: "Epilepsy",
    9: "Movement Disorders", 10: "Movement Disorders",
    11: "Movement Disorders", 12: "Movement Disorders",
    13: "Headache", 14: "Headache",
    15: "Headache", 16: "Headache",
    17: "Neuropathy", 18: "Neuropathy",
    19: "Neuropathy", 20: "Neuropathy",
}

# Expected cluster from generate_health_neuro.py
_CONCEPT_CLUSTER = {
    1: "stroke", 2: "stroke", 3: "stroke", 4: "xdn:imaging",
    5: "epilepsy", 6: "epilepsy", 7: "xdn:medication", 8: "epilepsy",
    9: "movement", 10: "movement", 11: "movement", 12: "xdn:medication",
    13: "headache", 14: "headache", 15: "headache", 16: "xdn:demographics",
    17: "neuropathy", 18: "neuropathy", 19: "neuropathy", 20: "xdn:lab_values",
}


def _parse_neuro_tinyid(tiny_id):
    """Parse synNR01T -> (concept_num=1, tier_letter='T')."""
    # Format: syn + NR + {NN} + {T|I|E}  (5 prefix chars)
    num = int(tiny_id[5:7])
    tier_letter = tiny_id[7]
    return num, tier_letter


def _get_subdomain(tiny_id):
    num, _ = _parse_neuro_tinyid(tiny_id)
    return _CONCEPT_SUBDOMAIN[num]


def _get_submodule(tiny_id):
    subdomain = _get_subdomain(tiny_id)
    return NESS_SUBMODULES[subdomain]


# ---------------------------------------------------------------------------
# Noise injection functions
# ---------------------------------------------------------------------------

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
        f"{orig_d}, assessed {TEMPORAL_PHRASE_LOWER}."
    )
    return noisy


def inject_tier2(rec):
    """Tier 2 (medium): instrument name only.

    - Designation 1 (name): prepend NESS sub-module
    - Definition: append anchor phrase with NESS
    """
    noisy = copy.deepcopy(rec)
    submodule = _get_submodule(rec["tinyId"])

    # Name: prepend instrument sub-module
    orig_name = noisy["designations"][0]["designation"]
    noisy["designations"][0]["designation"] = f"{submodule} - {orig_name}"

    # Definition: append anchor phrase
    orig_d = noisy["definitions"][0]["definition"]
    noisy["definitions"][0]["definition"] = (
        f"{orig_d} A component of the {NESS_PARENT}."
    )
    return noisy


def inject_tier3(rec):
    """Tier 3 (heavy): temporal + instrument + extra anchor.

    Combines Tier 1 + Tier 2 + additional NCRF anchor.
    """
    noisy = copy.deepcopy(rec)
    submodule = _get_submodule(rec["tinyId"])

    # Name: prepend instrument sub-module (Tier 2)
    orig_name = noisy["designations"][0]["designation"]
    noisy["designations"][0]["designation"] = f"{submodule} - {orig_name}"

    # Question: prepend temporal (Tier 1)
    orig_q = noisy["designations"][1]["designation"]
    noisy["designations"][1]["designation"] = (
        f"{TEMPORAL_PHRASE}, {orig_q[0].lower()}{orig_q[1:]}"
    )

    # Definition: temporal clause + NESS anchor + NCRF anchor
    orig_d = noisy["definitions"][0]["definition"]
    if orig_d.endswith("."):
        orig_d = orig_d[:-1]
    noisy["definitions"][0]["definition"] = (
        f"{orig_d}, assessed {TEMPORAL_PHRASE_LOWER}. "
        f"A component of the {NESS_PARENT}. "
        f"Based on the {NCRF_PARENT}."
    )
    return noisy


_TIER_FUNCS = {1: inject_tier1, 2: inject_tier2, 3: inject_tier3}
_TIER_LABELS = {1: "light", 2: "medium", 3: "heavy"}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_noisy_copies(source_records):
    """Generate 180 noisy CDEs (3 tiers x 60 originals)."""
    records = []
    for tier in (1, 2, 3):
        inject_fn = _TIER_FUNCS[tier]
        for rec in source_records:
            noisy = inject_fn(rec)
            noisy["tinyId"] = f"{rec['tinyId']}_t{tier}"
            records.append(noisy)
    return records


def generate_manifest(noisy_records, source_records):
    """Build manifest rows with noise metadata and source linkage."""
    rows = []
    for rec in noisy_records:
        tiny_id = rec["tinyId"]
        # Extract source tinyId and tier from "synNR01T_t1" format
        source_id = tiny_id.rsplit("_t", 1)[0]
        tier = int(tiny_id.rsplit("_t", 1)[1])

        concept_num, tier_letter = _parse_neuro_tinyid(source_id)
        subdomain = _CONCEPT_SUBDOMAIN[concept_num]
        verbosity = _TIER_SUFFIX[tier_letter]
        submodule = NESS_SUBMODULES[subdomain]
        expected_cluster = _CONCEPT_CLUSTER[concept_num]

        # Find source record for the name
        source_rec = next(r for r in source_records if r["tinyId"] == source_id)
        source_name = source_rec["designations"][0]["designation"]

        # Determine noise components
        if tier == 1:
            instrument = ""
            temporal = TEMPORAL_PHRASE
            anchor = ""
        elif tier == 2:
            instrument = submodule
            temporal = ""
            anchor = ""
        else:  # tier 3
            instrument = submodule
            temporal = TEMPORAL_PHRASE
            anchor = NCRF_PARENT

        rows.append({
            "tinyId": tiny_id,
            "domain": "neurology",
            "domain_full": "Neurology Assessment",
            "sub_domain": subdomain,
            "verbosity": verbosity,
            "concept_id": f"NR{concept_num:02d}",
            "expected_cluster": expected_cluster,
            "name": source_name,
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
        "verbosity", "concept_id", "expected_cluster", "name",
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
        description="Generate Health Neuro Drift: 180 noisy dose-tier copies "
                    "of health neuro CDEs for drift analysis."
    )
    parser.add_argument("--source", "-s", required=True,
                        help="Source JSON file (health neuro CDEs)")
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
    print(f"Generated {len(noisy_records)} neuro-drift CDEs -> {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) -> {manifest_path}")

    # Tier x verbosity breakdown
    tier_verb = {}
    for row in manifest_rows:
        key = (row["noise_tier"], row["verbosity"])
        tier_verb[key] = tier_verb.get(key, 0) + 1

    print("\nTier x Verbosity breakdown:")
    for (tier, verb), count in sorted(tier_verb.items()):
        print(f"  {tier:8s} x {verb:14s}: {count} CDEs")

    # Noise injection stats
    for tier_label in ("light", "medium", "heavy"):
        tier_rows = [r for r in manifest_rows if r["noise_tier"] == tier_label]
        has_inst = sum(1 for r in tier_rows if r["instrument"])
        has_temp = sum(1 for r in tier_rows if r["temporal_phrase"])
        has_anchor = sum(1 for r in tier_rows if r["anchor_phrase"])
        print(f"\n  {tier_label}: {len(tier_rows)} CDEs -- "
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
