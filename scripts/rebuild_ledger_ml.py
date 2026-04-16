#!/usr/bin/env python3
"""
Rebuild phrase_decisions.tsv from ML curation baseline.

Reads the existing GT phrase ledger (full pattern universe) and remaps
decisions based on the ML-curated pattern files:

  - Patterns in phrase_patterns.tsv → decision=keep (strip from CDE text)
  - Patterns in substitute_patterns.tsv → decision=substitute
  - All other patterns → decision=remove (skip, preserve in CDE text)

The ML phrase_patterns.tsv does NOT contain a decision column — all
patterns present in that file were curated as "to be stripped". The modify
decisions from the GT ledger need special handling: if the ML curator also
has the pattern (possibly with a different modification), it maps to keep;
if not, it maps to remove.

Usage:
    python rebuild_ledger_ml.py [--dry-run]

Reads from:
    data/reference_ledger/phrase_decisions.tsv         (GT, full universe)
    data/reference_ledger/production_patterns/phrase_patterns.tsv
    data/reference_ledger/production_patterns/substitute_patterns.tsv

Writes to:
    data/reference_ledger/phrase_decisions.tsv         (ML, overwritten)
    data/reference_ledger/phrase_decisions_curator_a.tsv      (backup of GT version)
"""

import csv
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = PROJECT_ROOT / "data" / "reference_ledger"
PROD_DIR = LEDGER_DIR / "production_patterns"

GT_DECISIONS = LEDGER_DIR / "phrase_decisions.tsv"
GT_BACKUP = LEDGER_DIR / "phrase_decisions_curator_a.tsv"
ML_PHRASE = PROD_DIR / "phrase_patterns.tsv"
ML_SUBSTITUTE = PROD_DIR / "substitute_patterns.tsv"

RUN_ID = "run_20260416_ml_formalization"
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")

LEDGER_HEADERS = [
    "pattern", "decision", "modification", "tinyIds",
    "n_tinyIds", "decided_at", "run_id", "notes",
]


def load_tsv_column(path: Path, col: str) -> set:
    """Load unique values from a TSV column."""
    values = set()
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            v = row.get(col, "").strip()
            if v:
                values.add(v)
    return values


def load_substitute_map(path: Path) -> dict:
    """Load pattern → replace_with mapping from substitute TSV."""
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            pattern = row.get("pattern", "").strip()
            replace_with = row.get("replace_with", "").strip()
            if pattern:
                mapping[pattern] = replace_with
    return mapping


def load_gt_ledger(path: Path) -> list:
    """Load all rows from the GT phrase decisions TSV."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
    return rows


def file_checksum(path: Path, algo: str = "md5") -> str:
    """Compute file checksum."""
    h = hashlib.new(algo)
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    dry_run = "--dry-run" in sys.argv

    # Load ML decision sets
    ml_strip_patterns = load_tsv_column(ML_PHRASE, "pattern")
    ml_substitute_map = load_substitute_map(ML_SUBSTITUTE)
    ml_substitute_patterns = set(ml_substitute_map.keys())

    print(f"ML strip patterns:      {len(ml_strip_patterns)}")
    print(f"ML substitute patterns: {len(ml_substitute_patterns)}")

    # Load GT ledger (full universe)
    gt_rows = load_gt_ledger(GT_DECISIONS)
    print(f"GT ledger patterns:     {len(gt_rows)}")

    # Remap decisions
    ml_rows = []
    counts = {"keep": 0, "remove": 0, "modify": 0, "substitute": 0}

    for row in gt_rows:
        pattern = row["pattern"]
        new_row = {
            "pattern": pattern,
            "tinyIds": row["tinyIds"],
            "n_tinyIds": row["n_tinyIds"],
            "decided_at": TIMESTAMP,
            "run_id": RUN_ID,
        }

        if pattern in ml_substitute_patterns:
            new_row["decision"] = "substitute"
            new_row["modification"] = ml_substitute_map[pattern]
            new_row["notes"] = "ML curation: substitute"
            counts["substitute"] += 1
        elif pattern in ml_strip_patterns:
            new_row["decision"] = "keep"
            new_row["modification"] = ""
            new_row["notes"] = "ML curation: strip"
            counts["keep"] += 1
        else:
            new_row["decision"] = "remove"
            new_row["modification"] = ""
            new_row["notes"] = "ML curation: skip"
            counts["remove"] += 1

        ml_rows.append(new_row)

    # Add ML patterns not in GT universe (from iterative harvesting or ML-specific curation)
    gt_patterns = {r["pattern"] for r in gt_rows}
    ml_only_strip = ml_strip_patterns - gt_patterns
    ml_only_sub = ml_substitute_patterns - gt_patterns

    # Load tinyIds from ML phrase file for patterns not in GT
    ml_tinyid_map = {}
    with open(ML_PHRASE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            p = row.get("pattern", "").strip()
            if p and p in ml_only_strip:
                tids = row.get("tinyIds", "")
                n = row.get("tinyid_count", str(len(tids.split())) if tids else "0")
                ml_tinyid_map[p] = (tids, n)

    for pattern in sorted(ml_only_strip):
        tids, n = ml_tinyid_map.get(pattern, ("", "0"))
        ml_rows.append({
            "pattern": pattern,
            "decision": "keep",
            "modification": "",
            "tinyIds": tids,
            "n_tinyIds": n,
            "decided_at": TIMESTAMP,
            "run_id": RUN_ID,
            "notes": "ML curation: strip (ML-only, not in GT universe)",
        })
        counts["keep"] += 1

    for pattern in sorted(ml_only_sub):
        ml_rows.append({
            "pattern": pattern,
            "decision": "substitute",
            "modification": ml_substitute_map[pattern],
            "tinyIds": "",
            "n_tinyIds": "0",
            "decided_at": TIMESTAMP,
            "run_id": RUN_ID,
            "notes": "ML curation: substitute (ML-only, not in GT universe)",
        })
        counts["substitute"] += 1

    if ml_only_strip:
        print(f"\nAdded {len(ml_only_strip)} ML-only strip patterns to ledger")
    if ml_only_sub:
        print(f"Added {len(ml_only_sub)} ML-only substitute patterns to ledger")

    print(f"\nML decision counts:")
    for dec, n in sorted(counts.items()):
        print(f"  {dec}: {n}")
    print(f"  total: {sum(counts.values())}")

    if dry_run:
        print("\n[DRY RUN] No files written.")
        return

    # Backup GT version
    if not GT_BACKUP.exists():
        shutil.copy2(GT_DECISIONS, GT_BACKUP)
        print(f"\nCurator A backup: {GT_BACKUP}")

    # Write new ML ledger
    with open(GT_DECISIONS, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_HEADERS, delimiter="\t")
        writer.writeheader()
        writer.writerows(ml_rows)

    n_lines = sum(1 for _ in open(GT_DECISIONS, "r", encoding="utf-8"))
    md5 = file_checksum(GT_DECISIONS, "md5")
    sha1 = file_checksum(GT_DECISIONS, "sha1")

    print(f"\nWritten: {GT_DECISIONS}")
    print(f"  lines: {n_lines}")
    print(f"  md5:   {md5}")
    print(f"  sha1:  {sha1}")


if __name__ == "__main__":
    main()
