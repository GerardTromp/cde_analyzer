#!/usr/bin/env python3
"""Compare new vs ref embeds, categorize all differences."""
import csv

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

print(f"New: {len(new)}, Ref: {len(ref)}")

# Categorize each difference
categories = {
    "indicator_of_whether": [],  # GT sub: "Indicator of whether" → "Indicator of"
    "indicator_whether": [],      # GT sub: "Indicator whether" → "Whether"
    "alsfrs": [],                 # ALSFRS-R abbreviation added today
    "other": [],
}

for tid in sorted(new.keys()):
    if tid not in ref or new[tid] == ref[tid]:
        continue

    n, r = new[tid], ref[tid]

    # Check: does the ref text contain "Indicator of" where new has raw text
    # without that prefix? This is the GT "Indicator of whether" → "Indicator of" sub.
    if "Indicator of whether" in n and "Indicator of whether" not in r:
        # New has original, ref has substituted version
        categories["indicator_of_whether"].append(tid)
    elif "Indicator whether" in n and "Indicator whether" not in r:
        categories["indicator_whether"].append(tid)
    elif "ALSFRS" in n or "ALSFRS" in r or "Amyotrophic" in n:
        categories["alsfrs"].append(tid)
    else:
        categories["other"].append(tid)

total_diff = sum(len(v) for v in categories.values())
print(f"\nTotal differences: {total_diff}")
for cat, tids in sorted(categories.items()):
    print(f"  {cat}: {len(tids)}")

# Show samples of each category
for cat, tids in sorted(categories.items()):
    if not tids:
        continue
    print(f"\n=== {cat} ({len(tids)} tinyIds) ===")
    for tid in tids[:3]:
        n, r = new[tid], ref[tid]
        # Find the first difference
        for i, (a, b) in enumerate(zip(n, r)):
            if a != b:
                start = max(0, i - 30)
                end = min(len(n), i + 50)
                print(f"  {tid} (diff at char {i}):")
                print(f"    NEW: ...{n[start:end]}...")
                print(f"    REF: ...{r[start:end]}...")
                break
        else:
            # Length difference
            print(f"  {tid} (length diff: new={len(n)}, ref={len(r)})")
            print(f"    NEW tail: ...{n[-80:]}")
            print(f"    REF tail: ...{r[-80:]}")
