#!/usr/bin/env python3
"""
Generate predefined strip pattern TSVs for all synthetic QC datasets.

Produces ready-to-use pattern files that the CDE Analyzer strip pipeline
can consume to cleanly remove instrument, temporal, and anchor noise from
any combination of synthetic datasets.

Usage:
    python scripts/generate_synthetic_strip_patterns.py \\
        -o data/synthetic_qc/strip_patterns/

Output files:
    inst_full_patterns.tsv   Parent instrument names (full instrument removal)
    inst_sub_patterns.tsv    Sub-scale/module names (sub-group removal)
    phrase_patterns.tsv      Temporal + anchor phrases
    all_patterns.tsv         Combined (all of the above)

Each file uses the standard pattern TSV format:
    pattern  tinyIds  type  source  decision

The tinyIds column lists which CDEs contain that pattern, drawn from
the manifest TSVs of each dataset.  This allows the strip pipeline
to apply patterns selectively by tinyId.
"""

import argparse
import csv
import json
import os
from collections import defaultdict


# ---------------------------------------------------------------------------
# Complete inventory of synthetic instruments across all datasets
# ---------------------------------------------------------------------------

# Each entry: (pattern_text, type, source_dataset, role)
# role: "parent" -> inst_full, "subscale" -> inst_sub

INSTRUMENTS = [
    # --- set1a_urban: ESI + CRAT ---
    ("Environmental Stress Index (ESI)",                "instrument", "set1a_urban", "parent"),
    ("ESI Heat Exposure",                               "instrument", "set1a_urban", "subscale"),
    ("ESI Water Stress",                                "instrument", "set1a_urban", "subscale"),
    ("ESI Air Contamination",                           "instrument", "set1a_urban", "subscale"),
    ("Community Resilience Assessment Tool (CRAT)",     "instrument", "set1a_urban", "parent"),
    ("CRAT Infrastructure Vulnerability",               "instrument", "set1a_urban", "subscale"),
    ("CRAT Environmental Burden",                       "instrument", "set1a_urban", "subscale"),
    ("CRAT Health Impact",                              "instrument", "set1a_urban", "subscale"),

    # --- set1b_clinical: SSS + FAB ---
    ("Symptom Severity Scale (SSS)",                    "instrument", "set1b_clinical", "parent"),
    ("SSS Pain Interference",                           "instrument", "set1b_clinical", "subscale"),
    ("SSS Cognitive Difficulty",                        "instrument", "set1b_clinical", "subscale"),
    ("SSS Sleep Disturbance",                           "instrument", "set1b_clinical", "subscale"),
    ("Functional Assessment Battery (FAB)",             "instrument", "set1b_clinical", "parent"),
    ("FAB Physical Function",                           "instrument", "set1b_clinical", "subscale"),
    ("FAB Daily Living Activities",                     "instrument", "set1b_clinical", "subscale"),
    ("FAB Emotional Well-Being",                        "instrument", "set1b_clinical", "subscale"),

    # --- set2_noisy: EMP + FSQA ---
    ("Environmental Monitoring Protocol (EMP)",         "instrument", "set2_noisy", "parent"),
    ("EMP Atmospheric Analysis",                        "instrument", "set2_noisy", "subscale"),
    ("EMP Aquatic Assessment",                          "instrument", "set2_noisy", "subscale"),
    ("EMP Pedological Survey",                          "instrument", "set2_noisy", "subscale"),
    ("Field Sampling Quality Assurance (FSQA)",         "instrument", "set2_noisy", "parent"),

    # --- health_drift: CMP + HDQF ---
    ("Clinical Monitoring Protocol (CMP)",              "instrument", "health_drift", "parent"),
    ("CMP Cardiac Assessment",                          "instrument", "health_drift", "subscale"),
    ("CMP Pulmonary Evaluation",                        "instrument", "health_drift", "subscale"),
    ("CMP Metabolic Panel",                             "instrument", "health_drift", "subscale"),
    ("Health Data Quality Framework (HDQF)",            "instrument", "health_drift", "parent"),

    # --- health_gravity_a: PHI + COAS ---
    ("Patient Health Inventory (PHI)",                  "instrument", "health_gravity_a", "parent"),
    ("PHI Emotional Distress",                          "instrument", "health_gravity_a", "subscale"),
    ("PHI Physical Limitation",                         "instrument", "health_gravity_a", "subscale"),
    ("PHI Digestive Function",                          "instrument", "health_gravity_a", "subscale"),
    ("Clinical Outcome Assessment Scale (COAS)",        "instrument", "health_gravity_a", "parent"),
    ("COAS Psychological Well-Being",                   "instrument", "health_gravity_a", "subscale"),
    ("COAS Rehabilitation Progress",                    "instrument", "health_gravity_a", "subscale"),
    ("COAS Somatic Symptom Burden",                     "instrument", "health_gravity_a", "subscale"),

    # --- health_neuro_drift: NESS + NCRF ---
    ("Neurological Examination Standardized Scale (NESS)", "instrument", "health_neuro_drift", "parent"),
    ("NESS Cerebrovascular Module",                     "instrument", "health_neuro_drift", "subscale"),
    ("NESS Seizure Module",                             "instrument", "health_neuro_drift", "subscale"),
    ("NESS Motor Function Module",                      "instrument", "health_neuro_drift", "subscale"),
    ("NESS Cephalgia Module",                           "instrument", "health_neuro_drift", "subscale"),
    ("NESS Peripheral Nerve Module",                    "instrument", "health_neuro_drift", "subscale"),
    ("Neurology Clinical Research Framework (NCRF)",    "instrument", "health_neuro_drift", "parent"),
]

# Anchor phrases injected into definitions
ANCHOR_PHRASES = [
    # "As part of" anchors (set1a, set1b, health_gravity_a)
    ("As part of the Environmental Stress Index (ESI)",                  "anchor", "set1a_urban"),
    ("Based on the Community Resilience Assessment Tool (CRAT)",        "anchor", "set1a_urban"),
    ("As part of the Symptom Severity Scale (SSS)",                     "anchor", "set1b_clinical"),
    ("Based on the Functional Assessment Battery (FAB)",                "anchor", "set1b_clinical"),
    ("As part of the Patient Health Inventory (PHI)",                   "anchor", "health_gravity_a"),
    ("Based on the Clinical Outcome Assessment Scale (COAS)",           "anchor", "health_gravity_a"),

    # "A field of" anchors (set2_noisy, health_drift)
    ("A field of the Environmental Monitoring Protocol (EMP)",          "anchor", "set2_noisy"),
    ("Based on the Field Sampling Quality Assurance (FSQA)",            "anchor", "set2_noisy"),
    ("A field of the Clinical Monitoring Protocol (CMP)",               "anchor", "health_drift"),
    ("Based on the Health Data Quality Framework (HDQF)",               "anchor", "health_drift"),

    # "A component of" anchors (health_neuro_drift)
    ("A component of the Neurological Examination Standardized Scale (NESS)", "anchor", "health_neuro_drift"),
    ("Based on the Neurology Clinical Research Framework (NCRF)",       "anchor", "health_neuro_drift"),
]

# Temporal phrases
TEMPORAL_PHRASES = [
    ("Over the past 30 days",       "temporal", "set1a_urban,set2_noisy,health_drift"),
    ("over the past 30 days",       "temporal", "set2_noisy,health_drift"),
    ("During the last 12 months",   "temporal", "set1a_urban"),
    ("In the past 7 days",          "temporal", "set1a_urban,set1b_clinical,health_gravity_a"),
    ("Over the past 2 weeks",       "temporal", "set1b_clinical,health_gravity_a"),
    ("During the past 4 weeks",     "temporal", "set1b_clinical,health_gravity_a"),
    ("During the past 6 months",    "temporal", "health_neuro_drift"),
    ("during the past 6 months",    "temporal", "health_neuro_drift"),
]

# Temporal clause fragments as they appear in definitions
TEMPORAL_CLAUSES = [
    ("measured over the past 30 days",      "temporal_clause", "set2_noisy,health_drift"),
    ("assessed during the past 6 months",   "temporal_clause", "health_neuro_drift"),
]


# ---------------------------------------------------------------------------
# TinyId resolution from manifests
# ---------------------------------------------------------------------------

def _load_manifest(path):
    """Load a manifest TSV into a list of dicts."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _find_tinyids_containing(manifests, pattern_text):
    """Find all tinyIds whose noisy fields would contain pattern_text.

    For instruments: check the 'instrument' column in drift/gravity manifests.
    For anchors/temporal: check 'anchor_phrase' and 'temporal_phrase' columns.
    Also check by scanning the actual JSON records if available.
    """
    tinyids = set()
    for mf_rows in manifests.values():
        for row in mf_rows:
            # Check instrument column
            if row.get("instrument", "") and pattern_text in row.get("instrument", ""):
                tinyids.add(row["tinyId"])
            # Check anchor_phrase column
            if row.get("anchor_phrase", "") and pattern_text in row.get("anchor_phrase", ""):
                tinyids.add(row["tinyId"])
            # Check temporal_phrase column
            if row.get("temporal_phrase", "") and pattern_text in row.get("temporal_phrase", ""):
                tinyids.add(row["tinyId"])
    return tinyids


def _find_tinyids_by_instrument_exact(manifests, instrument_name):
    """Find tinyIds where the instrument column exactly matches."""
    tinyids = set()
    for mf_rows in manifests.values():
        for row in mf_rows:
            if row.get("instrument", "") == instrument_name:
                tinyids.add(row["tinyId"])
    return tinyids


def _find_tinyids_by_source(manifests, source_datasets):
    """Find all tinyIds from the given source datasets."""
    tinyids = set()
    sources = set(source_datasets.split(","))
    for name, mf_rows in manifests.items():
        if name in sources:
            for row in mf_rows:
                tinyids.add(row["tinyId"])
    return tinyids


# ---------------------------------------------------------------------------
# Pattern TSV writing
# ---------------------------------------------------------------------------

def _write_pattern_tsv(rows, path):
    """Write pattern TSV file."""
    fields = ["pattern", "tinyIds", "type", "source", "decision"]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _make_row(pattern, tinyids, ptype, source, decision="keep"):
    """Build a pattern row dict."""
    return {
        "pattern": pattern,
        "tinyIds": ",".join(sorted(tinyids)) if tinyids else "",
        "type": ptype,
        "source": source,
        "decision": decision,
    }


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate predefined strip pattern TSVs for all "
                    "synthetic QC datasets."
    )
    parser.add_argument("-o", "--output-dir", required=True,
                        help="Output directory for pattern TSVs")
    parser.add_argument("--data-dir", default="data/synthetic_qc",
                        help="Root of synthetic QC data (default: data/synthetic_qc)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    data = args.data_dir

    # Load all manifests
    manifests = {}
    manifest_paths = {
        "set1a_urban":         os.path.join(data, "set1a_urban", "set1a_urban_manifest.tsv"),
        "set1b_clinical":      os.path.join(data, "set1b_clinical", "set1b_clinical_manifest.tsv"),
        "set2_noisy":          os.path.join(data, "set2_noisy", "set2_noisy_manifest.tsv"),
        "health_drift":        os.path.join(data, "health_drift", "health_drift_manifest.tsv"),
        "health_gravity_a":    os.path.join(data, "health_gravity_a", "health_gravity_a_manifest.tsv"),
        "health_neuro_drift":  os.path.join(data, "health_neuro_drift", "health_neuro_drift_manifest.tsv"),
    }
    for name, path in manifest_paths.items():
        rows = _load_manifest(path)
        if rows:
            manifests[name] = rows
            print(f"  Loaded {name}: {len(rows)} rows")
        else:
            print(f"  WARNING: {name} manifest not found at {path}")

    # --- Build inst_full_patterns.tsv (parent instruments) ---
    inst_full_rows = []
    for pattern, ptype, source, role in INSTRUMENTS:
        if role != "parent":
            continue
        tinyids = _find_tinyids_containing(manifests, pattern)
        if not tinyids:
            # Fall back to dataset-level tinyIds
            tinyids = _find_tinyids_by_source(manifests, source)
        inst_full_rows.append(_make_row(pattern, tinyids, "inst_full", source))

    inst_full_path = os.path.join(args.output_dir, "inst_full_patterns.tsv")
    _write_pattern_tsv(inst_full_rows, inst_full_path)
    print(f"\ninst_full_patterns.tsv: {len(inst_full_rows)} patterns")

    # --- Build inst_sub_patterns.tsv (sub-scale names) ---
    inst_sub_rows = []
    for pattern, ptype, source, role in INSTRUMENTS:
        if role != "subscale":
            continue
        tinyids = _find_tinyids_by_instrument_exact(manifests, pattern)
        if not tinyids:
            tinyids = _find_tinyids_containing(manifests, pattern)
        inst_sub_rows.append(_make_row(pattern, tinyids, "inst_sub", source))

    inst_sub_path = os.path.join(args.output_dir, "inst_sub_patterns.tsv")
    _write_pattern_tsv(inst_sub_rows, inst_sub_path)
    print(f"inst_sub_patterns.tsv: {len(inst_sub_rows)} patterns")

    # --- Build phrase_patterns.tsv (temporal + anchor phrases) ---
    phrase_rows = []

    # Temporal phrases
    for pattern, ptype, sources in TEMPORAL_PHRASES:
        tinyids = _find_tinyids_containing(manifests, pattern)
        if not tinyids:
            tinyids = _find_tinyids_by_source(manifests, sources)
        phrase_rows.append(_make_row(pattern, tinyids, "temporal", sources))

    # Temporal clauses (as they appear embedded in definitions)
    for pattern, ptype, sources in TEMPORAL_CLAUSES:
        tinyids = _find_tinyids_by_source(manifests, sources)
        phrase_rows.append(_make_row(pattern, tinyids, "temporal_clause", sources))

    # Anchor phrases
    for pattern, ptype, source in ANCHOR_PHRASES:
        tinyids = _find_tinyids_containing(manifests, pattern)
        if not tinyids:
            tinyids = _find_tinyids_by_source(manifests, source)
        phrase_rows.append(_make_row(pattern, tinyids, "anchor", source))

    phrase_path = os.path.join(args.output_dir, "phrase_patterns.tsv")
    _write_pattern_tsv(phrase_rows, phrase_path)
    print(f"phrase_patterns.tsv: {len(phrase_rows)} patterns")

    # --- Build all_patterns.tsv (combined) ---
    all_rows = inst_full_rows + inst_sub_rows + phrase_rows
    all_path = os.path.join(args.output_dir, "all_patterns.tsv")
    _write_pattern_tsv(all_rows, all_path)
    print(f"all_patterns.tsv: {len(all_rows)} patterns (combined)")

    # Summary
    print(f"\nTotal: {len(all_rows)} strip patterns across "
          f"{len(manifests)} datasets")
    print(f"Output directory: {args.output_dir}")

    # Per-dataset coverage
    dataset_patterns = defaultdict(int)
    for pattern, ptype, source, role in INSTRUMENTS:
        for s in source.split(","):
            dataset_patterns[s.strip()] += 1
    for pattern, ptype, sources in TEMPORAL_PHRASES + TEMPORAL_CLAUSES:
        for s in sources.split(","):
            dataset_patterns[s.strip()] += 1
    for pattern, ptype, source in ANCHOR_PHRASES:
        for s in source.split(","):
            dataset_patterns[s.strip()] += 1

    print("\nPatterns per dataset:")
    for ds, count in sorted(dataset_patterns.items()):
        print(f"  {ds}: {count} patterns")


if __name__ == "__main__":
    main()
