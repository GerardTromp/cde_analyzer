#!/usr/bin/env python3
"""Purge false-positive tinyIds from curation TSV files.

For each pattern in the TSV, verifies every listed tinyId by checking
whether the pattern actually appears (at word boundaries) in that CDE's
definition or designation texts.  TinyIds that don't genuinely match are
removed.  The tinyid_count column is updated accordingly.

Usage:
    python purge_false_tinyids.py INPUT_JSON TSV_FILE [-o OUTPUT_TSV] [--dry-run]

If -o is omitted, rewrites TSV_FILE in place.
--dry-run prints a summary without writing.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def build_text_index(cde_json_path: str) -> dict[str, list[str]]:
    """Build tinyId → list of text strings from CDE JSON."""
    with open(cde_json_path, "r", encoding="utf-8") as f:
        cdes = json.load(f)

    index: dict[str, list[str]] = {}
    for cde in cdes:
        tiny_id = cde.get("tinyId", "")
        if not tiny_id:
            continue
        texts = []
        for defn in cde.get("definitions", []):
            t = defn.get("definition", "")
            if t:
                texts.append(t)
        for desig in cde.get("designations", []):
            t = desig.get("designation", "")
            if t:
                texts.append(t)
        if texts:
            index[tiny_id] = texts
    return index


def pattern_matches_text(pattern: str, text: str) -> bool:
    """Check if pattern appears in text at word boundaries (case-sensitive).

    Uses \\b for word-character boundaries.  For patterns starting/ending
    with non-word characters (brackets, hyphens, etc.) plain substring
    match is used at that end since \\b cannot anchor there and mid-word
    false positives are not possible with non-alphanumeric edges.

    Trailing phrase-terminating punctuation (`` -``, `` ?``) is stripped
    before matching — these are extraction artifacts, not content.  The
    match uses the trimmed core so that "Quality of Life -" correctly
    finds "Quality of Life" at a word boundary.
    """
    # Strip trailing phrase-terminating punctuation (space + punct)
    core = re.sub(r'[\s]+[-?]+$', '', pattern)
    if not core:
        core = pattern  # safety: don't reduce to empty

    escaped = re.escape(core)
    # \b only works at word-character edges
    left = r'\b' if core and core[0].isalnum() else ''
    right = r'\b' if core and core[-1].isalnum() else ''
    return bool(re.search(left + escaped + right, text))


def purge_tsv(json_path: str, tsv_path: str, output_path: str | None,
              dry_run: bool = False, remove_empty: bool = False):
    """Main purge logic."""
    print(f"Loading CDE JSON: {json_path}")
    text_index = build_text_index(json_path)
    print(f"  Indexed {len(text_index)} CDEs with text")

    # Read TSV
    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("ERROR: No headers found in TSV")
            sys.exit(1)
        rows = list(reader)

    print(f"  Read {len(rows)} patterns from {tsv_path}")

    if "tinyIds" not in fieldnames or "pattern" not in fieldnames:
        print("ERROR: TSV must have 'pattern' and 'tinyIds' columns")
        sys.exit(1)

    has_count_col = "tinyid_count" in fieldnames

    # Process each row
    total_removed = 0
    total_original = 0
    patterns_affected = 0
    worst_cases: list[tuple[str, int, int]] = []  # (pattern, original, removed)

    for row in rows:
        pattern = row["pattern"]
        tinyids_str = row.get("tinyIds", "")
        if not tinyids_str:
            continue

        # tinyIds may be pipe-separated or space-separated
        sep = "|" if "|" in tinyids_str else " "
        original_ids = [t.strip() for t in tinyids_str.split(sep) if t.strip()]
        total_original += len(original_ids)

        # Verify each tinyId
        verified_ids = []
        for tid in original_ids:
            texts = text_index.get(tid, [])
            if not texts:
                # tinyId not in JSON — keep it (might be from a different source)
                verified_ids.append(tid)
                continue
            if any(pattern_matches_text(pattern, t) for t in texts):
                verified_ids.append(tid)

        removed = len(original_ids) - len(verified_ids)
        if removed > 0:
            total_removed += removed
            patterns_affected += 1
            worst_cases.append((pattern, len(original_ids), removed))

            # Update row (preserve original separator)
            row["tinyIds"] = sep.join(verified_ids)
            if has_count_col:
                row["tinyid_count"] = str(len(verified_ids))

    # Remove rows whose tinyIds are now empty
    empty_patterns = []
    if remove_empty:
        kept_rows = []
        for row in rows:
            tinyids_str = row.get("tinyIds", "")
            if not tinyids_str.strip():
                empty_patterns.append(row["pattern"])
            else:
                kept_rows.append(row)
        rows = kept_rows

    # Report
    print(f"\n--- Purge Summary ---")
    print(f"  Patterns scanned:  {len(rows) + len(empty_patterns)}")
    print(f"  Patterns affected: {patterns_affected}")
    print(f"  TinyIds original:  {total_original}")
    print(f"  TinyIds removed:   {total_removed}")
    print(f"  TinyIds remaining: {total_original - total_removed}")
    if empty_patterns:
        print(f"  Patterns deleted (0 tinyIds): {len(empty_patterns)}")
        for pat in empty_patterns:
            display = pat[:70] + "..." if len(pat) > 70 else pat
            print(f"    - {display}")
    print(f"  Rows in output:    {len(rows)}")

    if worst_cases:
        worst_cases.sort(key=lambda x: -x[2])
        print(f"\n  Top 20 worst affected patterns:")
        for pat, orig, rem in worst_cases[:20]:
            display = pat[:60] + "..." if len(pat) > 60 else pat
            print(f"    {orig:4d} → {orig-rem:4d}  (-{rem:3d})  {display}")

    if dry_run:
        print("\n  [DRY RUN — no files modified]")
        return

    # Write output
    out = output_path or tsv_path
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                                quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  Written to: {out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("json_path", help="Source CDE JSON file")
    parser.add_argument("tsv_path", help="Curation TSV file to purge")
    parser.add_argument("-o", "--output", help="Output TSV (default: overwrite input)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary without writing")
    parser.add_argument("--remove-empty", action="store_true",
                        help="Delete rows that lose all tinyIds")
    args = parser.parse_args()
    purge_tsv(args.json_path, args.tsv_path, args.output, args.dry_run,
              args.remove_empty)


if __name__ == "__main__":
    main()
