#!/usr/bin/env python3
"""
Oracle stripper for synthetic QC datasets.

Produces the "ideal" stripped output by reversing known injections.
For drift sets (set2, health_drift, health_neuro_drift): uses the base
JSON directly — the noise was added to copies of clean CDEs, so the base
content IS the ground truth.  For gravity sets (set1a, set1b, health_gravity_a):
imports the generator module and rebuilds CDEs from the pre-injection
topic data.

Usage:
    python scripts/oracle_strip_synthetic.py \
        --data-dir data/synthetic_qc \
        -o data/synthetic_qc/oracle_stripped

Output:
    Per-dataset stripped JSONs + combined_all.json (all CDEs for embedding)
    + oracle_report.tsv (per-CDE summary of what was removed)
"""

import argparse
import copy
import csv
import importlib.util
import json
import os
import sys


# ---------------------------------------------------------------------------
# Module importer for generator scripts
# ---------------------------------------------------------------------------

def _import_generator(script_path, module_name):
    """Import a generator script as a module."""
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    mod = importlib.util.module_from_spec(spec)
    # Prevent the module from running main() on import
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Gravity set oracle: rebuild from pre-injection topic data
# ---------------------------------------------------------------------------

def _oracle_gravity(generator_path, module_name):
    """Build clean CDE records from a gravity generator's topic data.

    Returns list of CDE dicts with no injected noise.
    """
    mod = _import_generator(generator_path, module_name)

    records = []
    for prefix, topic, tag, _ in mod._TOPICS:
        for i, (name, question, defn) in enumerate(topic):
            tiny_id = mod._make_tiny_id(prefix, i + 1)
            rec = mod._build_record(tiny_id, name, question, defn, tag)
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Drift set oracle: copy base content with noisy tinyIds
# ---------------------------------------------------------------------------

def _oracle_drift(noisy_json_path, base_json_path):
    """Build clean CDE records by copying base content for each noisy CDE.

    Returns list of CDE dicts with noisy tinyIds but clean content.
    """
    with open(base_json_path, "r", encoding="utf-8") as f:
        base_records = json.load(f)

    with open(noisy_json_path, "r", encoding="utf-8") as f:
        noisy_records = json.load(f)

    # Index base records by tinyId
    base_by_id = {r["tinyId"]: r for r in base_records}

    clean_records = []
    for noisy in noisy_records:
        # Extract source tinyId: "synAIR001_t1" -> "synAIR001"
        source_id = noisy["tinyId"].rsplit("_t", 1)[0]
        base = base_by_id[source_id]

        # Deep copy base, assign noisy tinyId
        clean = copy.deepcopy(base)
        clean["tinyId"] = noisy["tinyId"]
        clean_records.append(clean)

    return clean_records


# ---------------------------------------------------------------------------
# Diff report: compare noisy vs oracle to document what was removed
# ---------------------------------------------------------------------------

def _diff_fields(noisy_rec, clean_rec):
    """Compare noisy and clean CDE records, return a diff summary."""
    diffs = []

    # Compare designations
    for i, field_name in enumerate(["name", "question"]):
        noisy_val = noisy_rec["designations"][i]["designation"]
        clean_val = clean_rec["designations"][i]["designation"]
        if noisy_val != clean_val:
            removed = noisy_val.replace(clean_val, "").strip()
            if not removed:
                # Clean value is not a substring — compute prefix/suffix diff
                removed = f"[modified: {len(noisy_val)} -> {len(clean_val)} chars]"
            diffs.append((field_name, removed))

    # Compare definitions
    if noisy_rec.get("definitions") and clean_rec.get("definitions"):
        noisy_def = noisy_rec["definitions"][0]["definition"]
        clean_def = clean_rec["definitions"][0]["definition"]
        if noisy_def != clean_def:
            # The noise is typically appended or the trailing period is modified
            removed = noisy_def[len(clean_def):].strip() if noisy_def.startswith(clean_def) else ""
            if not removed:
                # Definition was modified (e.g., period removed + clause appended)
                removed = f"[definition modified: {len(noisy_def)} -> {len(clean_def)} chars]"
            diffs.append(("definition", removed))

    return diffs


def _build_report(noisy_records, clean_records, dataset_name):
    """Build report rows comparing noisy vs clean."""
    rows = []
    for noisy, clean in zip(noisy_records, clean_records):
        assert noisy["tinyId"] == clean["tinyId"], \
            f"tinyId mismatch: {noisy['tinyId']} vs {clean['tinyId']}"

        diffs = _diff_fields(noisy, clean)
        if diffs:
            for field, removed in diffs:
                rows.append({
                    "dataset": dataset_name,
                    "tinyId": noisy["tinyId"],
                    "field": field,
                    "removed_text": removed,
                })
        else:
            rows.append({
                "dataset": dataset_name,
                "tinyId": noisy["tinyId"],
                "field": "(clean)",
                "removed_text": "",
            })
    return rows


# ---------------------------------------------------------------------------
# Dataset definitions
# ---------------------------------------------------------------------------

# Gravity sets: (dataset_name, generator_script, noisy_json)
GRAVITY_SETS = [
    ("set1a_urban",
     "generate_synthetic_set1a.py",
     "set1a_urban/set1a_urban.json"),
    ("set1b_clinical",
     "generate_synthetic_set1b.py",
     "set1b_clinical/set1b_clinical.json"),
    ("health_gravity_a",
     "generate_health_gravity_a.py",
     "health_gravity_a/health_gravity_a.json"),
]

# Drift sets: (dataset_name, noisy_json, base_json)
DRIFT_SETS = [
    ("set2_noisy",
     "set2_noisy/set2_noisy.json",
     "synthetic_cdes.json"),
    ("health_drift",
     "health_drift/health_drift.json",
     "health_base/health_base.json"),
    ("health_neuro_drift",
     "health_neuro_drift/health_neuro_drift.json",
     "health_neuro/health_neuro.json"),
]

# Base sets (already clean, included in combined output)
BASE_SETS = [
    ("base_mixed",      "synthetic_cdes.json"),
    ("base_health",     "health_base/health_base.json"),
    ("base_neuro",      "health_neuro/health_neuro.json"),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Oracle stripper: produce ideal stripped output for "
                    "synthetic QC datasets by reversing known injections."
    )
    parser.add_argument("--data-dir", default="data/synthetic_qc",
                        help="Root of synthetic QC data")
    parser.add_argument("--scripts-dir", default="scripts",
                        help="Directory containing generator scripts")
    parser.add_argument("-o", "--output-dir", required=True,
                        help="Output directory for stripped JSONs")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON output")
    parser.add_argument("--include-base", action="store_true",
                        help="Include base (clean) datasets in combined output")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    indent = 2 if args.pretty else None

    all_report_rows = []
    all_clean_records = []  # For combined output
    dataset_stats = []

    # --- Process gravity sets ---
    for ds_name, gen_script, noisy_json_rel in GRAVITY_SETS:
        gen_path = os.path.join(args.scripts_dir, gen_script)
        noisy_path = os.path.join(args.data_dir, noisy_json_rel)

        if not os.path.exists(gen_path):
            print(f"  SKIP {ds_name}: generator not found at {gen_path}")
            continue
        if not os.path.exists(noisy_path):
            print(f"  SKIP {ds_name}: noisy JSON not found at {noisy_path}")
            continue

        print(f"Processing {ds_name} (gravity)...")

        # Build clean records from generator topic data
        clean_records = _oracle_gravity(gen_path, gen_script.replace(".py", ""))

        # Load noisy for diff report
        with open(noisy_path, "r", encoding="utf-8") as f:
            noisy_records = json.load(f)

        # Sanity check: same count and tinyId order
        assert len(clean_records) == len(noisy_records), \
            f"{ds_name}: record count mismatch ({len(clean_records)} vs {len(noisy_records)})"
        for c, n in zip(clean_records, noisy_records):
            assert c["tinyId"] == n["tinyId"], \
                f"{ds_name}: tinyId order mismatch ({c['tinyId']} vs {n['tinyId']})"

        # Write stripped JSON
        out_path = os.path.join(args.output_dir, f"{ds_name}.json")
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(clean_records, f, indent=indent, ensure_ascii=False)
            f.write("\n")

        # Build diff report
        report_rows = _build_report(noisy_records, clean_records, ds_name)
        all_report_rows.extend(report_rows)
        all_clean_records.extend(clean_records)

        n_modified = sum(1 for r in report_rows if r["field"] != "(clean)")
        n_clean = sum(1 for r in report_rows if r["field"] == "(clean)")
        dataset_stats.append((ds_name, "gravity", len(clean_records),
                              n_modified, n_clean))
        print(f"  {len(clean_records)} CDEs -> {out_path}")
        print(f"  {n_modified} field modifications reversed, "
              f"{n_clean} already clean")

    # --- Process drift sets ---
    for ds_name, noisy_json_rel, base_json_rel in DRIFT_SETS:
        noisy_path = os.path.join(args.data_dir, noisy_json_rel)
        base_path = os.path.join(args.data_dir, base_json_rel)

        if not os.path.exists(noisy_path):
            print(f"  SKIP {ds_name}: noisy JSON not found at {noisy_path}")
            continue
        if not os.path.exists(base_path):
            print(f"  SKIP {ds_name}: base JSON not found at {base_path}")
            continue

        print(f"Processing {ds_name} (drift)...")

        # Build clean records by copying base content
        clean_records = _oracle_drift(noisy_path, base_path)

        # Load noisy for diff report
        with open(noisy_path, "r", encoding="utf-8") as f:
            noisy_records = json.load(f)

        # Write stripped JSON
        out_path = os.path.join(args.output_dir, f"{ds_name}.json")
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(clean_records, f, indent=indent, ensure_ascii=False)
            f.write("\n")

        # Build diff report
        report_rows = _build_report(noisy_records, clean_records, ds_name)
        all_report_rows.extend(report_rows)
        all_clean_records.extend(clean_records)

        n_modified = sum(1 for r in report_rows if r["field"] != "(clean)")
        dataset_stats.append((ds_name, "drift", len(clean_records),
                              n_modified, 0))
        print(f"  {len(clean_records)} CDEs -> {out_path}")
        print(f"  {n_modified} field modifications reversed")

    # --- Include base sets in combined output ---
    if args.include_base:
        for ds_name, json_rel in BASE_SETS:
            json_path = os.path.join(args.data_dir, json_rel)
            if not os.path.exists(json_path):
                print(f"  SKIP base {ds_name}: not found at {json_path}")
                continue
            with open(json_path, "r", encoding="utf-8") as f:
                base_records = json.load(f)
            all_clean_records.extend(base_records)
            print(f"Including {ds_name}: {len(base_records)} clean CDEs")

    # --- Write combined output ---
    combined_path = os.path.join(args.output_dir, "combined_all.json")
    with open(combined_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(all_clean_records, f, indent=indent, ensure_ascii=False)
        f.write("\n")
    print(f"\nCombined: {len(all_clean_records)} CDEs -> {combined_path}")

    # --- Write report TSV ---
    report_path = os.path.join(args.output_dir, "oracle_report.tsv")
    fields = ["dataset", "tinyId", "field", "removed_text"]
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_report_rows)
    print(f"Report: {len(all_report_rows)} rows -> {report_path}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("Oracle Strip Summary")
    print("=" * 60)
    total_cdes = 0
    total_mods = 0
    for ds_name, ds_type, n_cdes, n_mods, n_clean in dataset_stats:
        total_cdes += n_cdes
        total_mods += n_mods
        print(f"  {ds_name:25s} ({ds_type:7s}): "
              f"{n_cdes:4d} CDEs, {n_mods:4d} fields modified"
              + (f", {n_clean} clean" if n_clean else ""))

    print(f"\n  Total: {total_cdes} CDEs, {total_mods} field modifications")
    if args.include_base:
        n_base = len(all_clean_records) - total_cdes
        print(f"  + {n_base} base CDEs included in combined output")
    print(f"  Combined output: {len(all_clean_records)} CDEs")


if __name__ == "__main__":
    main()
