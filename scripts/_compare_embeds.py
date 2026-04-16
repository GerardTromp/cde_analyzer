#!/usr/bin/env python3
"""Compare new embed TSV against reference, report differences."""
import csv
import sys

NEW = "/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3/test_v7/validation/embed_MTSFPT.tsv"
REF = "/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3/test_v7/ML/embed_MTSFPT_ML.tsv"

def load_tsv(path):
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            data[row["tinyId"]] = row.get("embed_text", "")
    return data

new = load_tsv(NEW)
ref = load_tsv(REF)

print(f"New: {len(new)} records")
print(f"Ref: {len(ref)} records")

# Find differences
diffs = []
for tid in sorted(new.keys()):
    if tid not in ref:
        diffs.append((tid, "NEW_ONLY", "", ""))
    elif new[tid] != ref[tid]:
        diffs.append((tid, "CHANGED", new[tid][:150], ref[tid][:150]))

for tid in sorted(ref.keys()):
    if tid not in new:
        diffs.append((tid, "REF_ONLY", "", ""))

print(f"\nDifferences: {len(diffs)} tinyIds")
print(f"  CHANGED: {sum(1 for d in diffs if d[1] == 'CHANGED')}")
print(f"  NEW_ONLY: {sum(1 for d in diffs if d[1] == 'NEW_ONLY')}")
print(f"  REF_ONLY: {sum(1 for d in diffs if d[1] == 'REF_ONLY')}")

if not diffs:
    print("\nFiles are identical!")
    sys.exit(0)

# Categorize changes
indicator_of = []
alsfrs = []
other = []

for tid, dtype, new_text, ref_text in diffs:
    if dtype != "CHANGED":
        other.append((tid, dtype, new_text, ref_text))
        continue

    if "Indicator of whether" in ref_text or "Indicator whether" in ref_text:
        indicator_of.append(tid)
    elif "ALSFRS" in new_text or "ALSFRS" in ref_text or "Amyotrophic" in ref_text:
        alsfrs.append(tid)
    else:
        other.append((tid, dtype, new_text, ref_text))

print(f"\n--- Categorized changes ---")
print(f"GT-only substitutions (Indicator of whether/Indicator whether): {len(indicator_of)}")
print(f"ALSFRS-R abbreviation (new today): {len(alsfrs)}")
print(f"Other/uncategorized: {len(other)}")

if indicator_of:
    print(f"\nIndicator substitution tinyIds (first 5):")
    for tid in indicator_of[:5]:
        print(f"  {tid}")
        print(f"    NEW: {new[tid][:120]}")
        print(f"    REF: {ref[tid][:120]}")

if alsfrs:
    print(f"\nALSFRS-R tinyIds:")
    for tid in alsfrs:
        print(f"  {tid}")
        print(f"    NEW: {new[tid][:120]}")
        print(f"    REF: {ref[tid][:120]}")

if other:
    print(f"\nOther differences (first 10):")
    for tid, dtype, new_text, ref_text in other[:10]:
        print(f"  {tid} ({dtype})")
        if new_text:
            print(f"    NEW: {new_text[:120]}")
        if ref_text:
            print(f"    REF: {ref_text[:120]}")
