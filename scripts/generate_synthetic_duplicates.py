#!/usr/bin/env python3
"""
Generate synthetic duplicate and near-duplicate CDEs for redundancy detection QC.

Produces CDEs derived from the base set (generate_synthetic_cdes.py) in three
categories:

  1. **Exact duplicates** — identical content, different tinyId, original name
  2. **Labelled copies** — identical content, different tinyId, name prefixed
     with "Copy of {name}"
  3. **Near-duplicates** — same concept, slightly different wording (synonym
     substitution, reordering, minor rephrasing)

These test whether a redundancy / deduplication pipeline can detect both
trivial copies and semantically equivalent entries.

Usage:
    python scripts/generate_synthetic_duplicates.py -o data/synthetic_qc/duplicates/synthetic_duplicates.json
    python scripts/generate_synthetic_duplicates.py -o data/synthetic_qc/duplicates/synthetic_duplicates.json --pretty

Output: ~30 CDEs (10 exact + 10 labelled-copy + 10 near-duplicate)
"""

import os
import sys

# Allow importing the base generator and shared utilities
sys.path.insert(0, os.path.dirname(__file__))

from generate_synthetic_cdes import TOPIC_A_AIR, TOPIC_B_WATER, TOPIC_C_SOIL
from synthetic_common import (
    build_record, make_tiny_id, make_parser, ensure_output_dir,
    write_cde_json, write_manifest_tsv,
)


# ---------------------------------------------------------------------------
# Source CDEs to duplicate (index into the 20-per-topic arrays)
# Chosen to span domains + cross-domain groups for interesting test cases
# ---------------------------------------------------------------------------

# (source_topic, source_index_0based, source_prefix, domain_tag)
_SOURCES = [
    # Air — terse
    (TOPIC_A_AIR,   0,  "AIR", "Air Quality Monitoring"),       # PM2.5 concentration
    (TOPIC_A_AIR,   6,  "AIR", "Air Quality Monitoring"),       # Air Quality Index
    (TOPIC_A_AIR,  18,  "AIR", "Air Quality Monitoring"),       # Acidity of precipitation (xd:pH)
    (TOPIC_A_AIR,  10,  "AIR", "Air Quality Monitoring"),       # Ambient temperature (xd:temperature)
    # Water — informational
    (TOPIC_B_WATER,  0, "WAT", "Water Quality Assessment"),     # Dissolved oxygen
    (TOPIC_B_WATER,  1, "WAT", "Water Quality Assessment"),     # Water pH (xd:pH)
    (TOPIC_B_WATER, 11, "WAT", "Water Quality Assessment"),     # Lead in water (xd:heavy_metals)
    # Soil — expansive
    (TOPIC_C_SOIL,   0, "SOL", "Soil Composition Analysis"),    # Organic matter
    (TOPIC_C_SOIL,   4, "SOL", "Soil Composition Analysis"),    # Soil pH (xd:pH)
    (TOPIC_C_SOIL,   9, "SOL", "Soil Composition Analysis"),    # Lead in soil (xd:heavy_metals)
]


# ---------------------------------------------------------------------------
# Near-duplicate rewrites
# Same concepts as the 10 sources above, rephrased
# ---------------------------------------------------------------------------

_NEAR_DUPLICATES = [
    # 0: PM2.5 — terse
    (
        "Fine particulate matter concentration",
        "PM2.5 measurement value",
        "Concentration of fine particles (diameter <= 2.5 um) per cubic meter of air.",
    ),
    # 1: AQI — terse
    (
        "Overall Air Quality Index score",
        "AQI composite value",
        "Composite score summarizing overall quality of ambient air.",
    ),
    # 2: Acidity of precipitation — terse
    (
        "Precipitation pH",
        "pH of collected rainwater",
        "Hydrogen ion concentration in precipitation samples.",
    ),
    # 3: Ambient temperature — terse
    (
        "Air temperature at monitoring site",
        "Temperature of ambient air",
        "Temperature of the air recorded at the monitoring location.",
    ),
    # 4: Dissolved oxygen — informational
    (
        "Dissolved oxygen in water",
        "Oxygen concentration dissolved in the water sample",
        "The amount of molecular oxygen dissolved in the water, measured in "
        "milligrams per liter. Dissolved oxygen supports aquatic life and "
        "indicates the health of the aquatic ecosystem.",
    ),
    # 5: Water pH — informational
    (
        "pH of water sample",
        "Water acidity or alkalinity measurement",
        "The measure of hydrogen ion activity in a water sample on a "
        "logarithmic scale ranging from 0 to 14. A pH below 7 denotes acidic "
        "conditions; above 7 denotes alkaline conditions.",
    ),
    # 6: Lead in water — informational
    (
        "Dissolved lead in water sample",
        "Lead concentration in the water",
        "The amount of dissolved lead per unit volume of water, typically "
        "expressed in micrograms per liter. Lead is a regulated heavy metal "
        "because of its neurotoxic properties at low concentrations.",
    ),
    # 7: Organic matter — expansive
    (
        "Organic matter percentage in soil",
        "Proportion of organic material in the soil expressed as a percentage "
        "of total dry mass",
        "Soil organic matter comprises all living and dead biological material "
        "in the soil, including decomposed plant material, animal remains, "
        "microbial biomass, and humic compounds. It is determined by "
        "loss-on-ignition or wet oxidation and reported as a percentage of "
        "oven-dried soil weight. Organic matter content controls nutrient "
        "cycling, water-holding capacity, and soil structure.",
    ),
    # 8: Soil pH — expansive
    (
        "Soil pH in water suspension",
        "Hydrogen ion activity of the soil measured in a standardized "
        "soil-water slurry",
        "The pH of a soil is measured by suspending a known mass of air-dried "
        "soil in deionized water at a standard ratio, commonly one part soil "
        "to two parts water, and reading the hydrogen ion activity with a "
        "glass electrode. Soil pH affects nutrient availability, microbial "
        "processes, and the mobility of essential elements and potentially "
        "toxic metals. Values range from strongly acidic (below 4.5) to "
        "strongly alkaline (above 8.5).",
    ),
    # 9: Lead in soil — expansive
    (
        "Total lead content in soil",
        "Lead mass per unit dry weight of soil determined by acid digestion "
        "and instrumental measurement",
        "Total lead in soil is quantified by digesting a dried, ground sample "
        "in concentrated acid, filtering the digest, and analyzing the "
        "filtrate using inductively coupled plasma mass spectrometry or atomic "
        "absorption spectroscopy. The result is reported in milligrams per "
        "kilogram. Lead is a persistent heavy metal contaminant that "
        "accumulates in soil and poses health risks through direct contact, "
        "dust inhalation, and crop uptake.",
    ),
]


# ---------------------------------------------------------------------------
# Manifest metadata
# ---------------------------------------------------------------------------

# Maps source index to (sub_domain, expected_cluster) — mirrors base manifest
_SOURCE_MANIFEST = [
    ("Core Pollutants",    "air"),              # 0: PM2.5
    ("Core Pollutants",    "air"),              # 1: AQI
    ("pH Measurement",     "xd:pH"),            # 2: precipitation pH
    ("Meteorological",     "xd:temperature"),   # 3: ambient temperature
    ("Core Parameters",    "water"),            # 4: dissolved oxygen
    ("pH Measurement",     "xd:pH"),            # 5: water pH
    ("Heavy Metals",       "xd:heavy_metals"),  # 6: lead in water
    ("Core Composition",   "soil"),             # 7: organic matter
    ("pH Measurement",     "xd:pH"),            # 8: soil pH
    ("Heavy Metals",       "xd:heavy_metals"),  # 9: lead in soil
]

_DOMAIN_LABELS = {
    "Air Quality Monitoring":    "air_quality",
    "Water Quality Assessment":  "water_quality",
    "Soil Composition Analysis": "soil_composition",
}

_VERBOSITY = {
    "Air Quality Monitoring":    "terse",
    "Water Quality Assessment":  "informational",
    "Soil Composition Analysis": "expansive",
}

# Manifest fields (extended with dup_type and source_tinyid)
_MANIFEST_FIELDS = [
    "tinyId", "domain", "domain_full", "sub_domain",
    "verbosity", "expected_cluster", "name",
    "dup_type", "source_tinyid",
]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_all():
    """Return duplicate/near-duplicate CDE records + manifest rows."""
    records = []
    manifest = []

    for i, (topic, src_idx, src_prefix, domain_tag) in enumerate(_SOURCES):
        name, question, defn = topic[src_idx]
        source_tid = make_tiny_id(src_prefix, src_idx + 1)
        sub_domain, expected_cluster = _SOURCE_MANIFEST[i]
        domain_label = _DOMAIN_LABELS[domain_tag]
        verbosity = _VERBOSITY[domain_tag]

        # --- Exact duplicate (same content, new id) ---
        dup_tid = make_tiny_id("DUP", i + 1)
        rec = build_record(dup_tid, name, question, defn, domain_tag)
        records.append(rec)
        manifest.append({
            "tinyId": dup_tid,
            "domain": domain_label,
            "domain_full": domain_tag,
            "sub_domain": sub_domain,
            "verbosity": verbosity,
            "expected_cluster": expected_cluster,
            "name": name,
            "dup_type": "exact",
            "source_tinyid": source_tid,
        })

        # --- Labelled copy ("Copy of …") ---
        copy_tid = make_tiny_id("CPY", i + 1)
        copy_name = f"Copy of {name}"
        rec = build_record(copy_tid, copy_name, question, defn, domain_tag)
        records.append(rec)
        manifest.append({
            "tinyId": copy_tid,
            "domain": domain_label,
            "domain_full": domain_tag,
            "sub_domain": sub_domain,
            "verbosity": verbosity,
            "expected_cluster": expected_cluster,
            "name": copy_name,
            "dup_type": "labelled_copy",
            "source_tinyid": source_tid,
        })

        # --- Near-duplicate (rephrased) ---
        nd_name, nd_question, nd_defn = _NEAR_DUPLICATES[i]
        nd_tid = make_tiny_id("NDU", i + 1)
        rec = build_record(nd_tid, nd_name, nd_question, nd_defn, domain_tag)
        records.append(rec)
        manifest.append({
            "tinyId": nd_tid,
            "domain": domain_label,
            "domain_full": domain_tag,
            "sub_domain": sub_domain,
            "verbosity": verbosity,
            "expected_cluster": expected_cluster,
            "name": nd_name,
            "dup_type": "near_duplicate",
            "source_tinyid": source_tid,
        })

    return records, manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = make_parser(
        "Generate synthetic duplicate/near-duplicate CDEs for redundancy "
        "detection QC."
    )
    args = parser.parse_args()
    out_dir = ensure_output_dir(args.output)

    records, manifest_rows = generate_all()

    write_cde_json(records, args.output, pretty=args.pretty)

    manifest_path = args.manifest or os.path.join(
        out_dir, "duplicates_manifest.tsv"
    )
    write_manifest_tsv(manifest_rows, manifest_path, fields=_MANIFEST_FIELDS)

    # Summary
    by_type = {}
    for row in manifest_rows:
        by_type.setdefault(row["dup_type"], []).append(row["tinyId"])

    print(f"Generated {len(records)} duplicate/near-duplicate CDEs -> {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) -> {manifest_path}")
    for dtype, ids in sorted(by_type.items()):
        print(f"  {dtype}: {len(ids)} CDEs")

    # Show source linkage
    print(f"\nSource linkage (10 base CDEs -> 30 derived):")
    for row in manifest_rows:
        if row["dup_type"] == "exact":
            src = row["source_tinyid"]
            dup = row["tinyId"]
            cpy = dup.replace("DUP", "CPY")
            ndu = dup.replace("DUP", "NDU")
            print(f"  {src} -> {dup} (exact), {cpy} (copy), {ndu} (near-dup)")


if __name__ == "__main__":
    main()
