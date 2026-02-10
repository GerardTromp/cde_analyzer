#!/usr/bin/env python3
"""
Potential loss of information analysis for branching strip outputs.

Computes per-field word counts (all words, content words) for the original
input and each of the 5 branching strip outputs. Reports absolute counts
and percentage loss relative to the original.

Usage:
    python scripts/branching_loss_analysis.py \
        --original /path/to/cdes_subset.json \
        --branch-dir /path/to/branching_output \
        [--output /path/to/results.tsv]
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# Same stopwords as logic/phrase_grouper.py
STOPWORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'else',
    'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'from',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
    'will', 'would', 'could', 'should', 'may', 'might', 'must',
    'that', 'which', 'who', 'whom', 'whose', 'this', 'these', 'those',
    'it', 'its', 'as', 'so', 'than', 'such', 'no', 'not', 'only',
    'own', 'same', 'too', 'very', 'just', 'also', 'now', 'here',
    'there', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
    'both', 'few', 'more', 'most', 'other', 'some', 'any', 'can',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'under', 'over', 'out', 'up', 'down', 'about', 'again',
})

# Word tokenizer: splits on whitespace and strips punctuation
WORD_RE = re.compile(r'\b\w+\b')


def extract_field_texts(record: Dict, field: str) -> str:
    """Extract all text values from definitions.*.definition or designations.*.designation."""
    parts = []
    container_key = field.split('.')[0]  # "definitions" or "designations"
    leaf_key = field.split('.')[-1]       # "definition" or "designation"

    container = record.get(container_key, []) or []
    for item in container:
        val = item.get(leaf_key, "") or ""
        if val:
            parts.append(str(val))
    return " ".join(parts)


def count_words(text: str) -> Tuple[int, int, int]:
    """Return (total_words, content_words, stopwords) for text."""
    words = WORD_RE.findall(text.lower())
    total = len(words)
    stop = sum(1 for w in words if w in STOPWORDS)
    content = total - stop
    return total, content, stop


def analyze_file(filepath: str, fields: List[str]) -> Dict:
    """Analyze a JSON file, return per-field and aggregate word counts."""
    with open(filepath, encoding='utf-8') as f:
        records = json.load(f)

    results = {}
    for field in fields:
        total_words = 0
        total_content = 0
        total_stop = 0
        empty_count = 0

        per_record = []
        for rec in records:
            text = extract_field_texts(rec, field)
            tw, cw, sw = count_words(text)
            total_words += tw
            total_content += cw
            total_stop += sw
            if tw == 0:
                empty_count += 1
            per_record.append((tw, cw))

        results[field] = {
            'total_words': total_words,
            'content_words': total_content,
            'stopwords': total_stop,
            'empty_records': empty_count,
            'record_count': len(records),
            'per_record': per_record,
        }

    # Aggregate
    agg_tw = sum(r['total_words'] for r in results.values())
    agg_cw = sum(r['content_words'] for r in results.values())
    agg_sw = sum(r['stopwords'] for r in results.values())
    results['_aggregate'] = {
        'total_words': agg_tw,
        'content_words': agg_cw,
        'stopwords': agg_sw,
    }

    return results


def pct(part, whole):
    if whole == 0:
        return 0.0
    return 100.0 * part / whole


def compute_per_record_loss(orig_per_record, stripped_per_record):
    """Compute per-record content word loss percentiles."""
    losses = []
    for (otw, ocw), (stw, scw) in zip(orig_per_record, stripped_per_record):
        if ocw > 0:
            loss = 100.0 * (ocw - scw) / ocw
        else:
            loss = 0.0
        losses.append(loss)
    losses.sort()
    n = len(losses)
    if n == 0:
        return {}
    return {
        'min': losses[0],
        'p25': losses[n // 4],
        'median': losses[n // 2],
        'p75': losses[3 * n // 4],
        'p90': losses[int(n * 0.90)],
        'p95': losses[int(n * 0.95)],
        'max': losses[-1],
        'mean': sum(losses) / n,
    }


def main():
    parser = argparse.ArgumentParser(description="Branching strip loss-of-information analysis")
    parser.add_argument('--original', required=True, help='Original (unstripped) JSON file')
    parser.add_argument('--branch-dir', required=True, help='Directory with branching output JSON files')
    parser.add_argument('--output', '-o', default=None, help='Output TSV file (default: stdout)')
    args = parser.parse_args()

    fields = [
        'definitions.*.definition',
        'designations.*.designation',
    ]
    field_labels = {
        'definitions.*.definition': 'definition',
        'designations.*.designation': 'designation',
    }

    branch_files = {
        'inst_full': 'inst_full_stripped.json',
        'inst_sub': 'inst_sub_stripped.json',
        'phrase_only': 'phrase_stripped.json',
        'both_full': 'both_full_stripped.json',
        'both_sub': 'both_sub_stripped.json',
    }

    branch_dir = Path(args.branch_dir)

    # Analyze original
    print(f"Analyzing original: {args.original}", file=sys.stderr)
    orig = analyze_file(args.original, fields)

    # Analyze each branch
    branch_results = {}
    for label, filename in branch_files.items():
        filepath = branch_dir / filename
        if not filepath.exists():
            print(f"WARNING: {filepath} not found, skipping", file=sys.stderr)
            continue
        print(f"Analyzing {label}: {filepath}", file=sys.stderr)
        branch_results[label] = analyze_file(str(filepath), fields)

    # --- Print Summary Table ---
    out = open(args.output, 'w', encoding='utf-8') if args.output else sys.stdout

    # Table 1: Absolute word counts per file/field
    print("\n" + "=" * 90, file=out)
    print("TABLE 1: Word Counts by File and Field", file=out)
    print("=" * 90, file=out)
    header = f"{'File':<18} {'Field':<14} {'Total':>8} {'Content':>8} {'Stop':>8} {'Empty':>6} {'Records':>8}"
    print(header, file=out)
    print("-" * 90, file=out)

    for field in fields:
        fl = field_labels[field]
        r = orig[field]
        print(f"{'original':<18} {fl:<14} {r['total_words']:>8,} {r['content_words']:>8,} {r['stopwords']:>8,} {r['empty_records']:>6} {r['record_count']:>8}", file=out)

    for label, data in branch_results.items():
        for field in fields:
            fl = field_labels[field]
            r = data[field]
            print(f"{label:<18} {fl:<14} {r['total_words']:>8,} {r['content_words']:>8,} {r['stopwords']:>8,} {r['empty_records']:>6} {r['record_count']:>8}", file=out)

    # Table 2: Loss relative to original
    print("\n" + "=" * 90, file=out)
    print("TABLE 2: Word Loss Relative to Original (per field)", file=out)
    print("=" * 90, file=out)
    header2 = f"{'File':<18} {'Field':<14} {'Words Lost':>10} {'% Total':>8} {'Content Lost':>12} {'% Content':>10}"
    print(header2, file=out)
    print("-" * 90, file=out)

    for label, data in branch_results.items():
        for field in fields:
            fl = field_labels[field]
            otw = orig[field]['total_words']
            ocw = orig[field]['content_words']
            stw = data[field]['total_words']
            scw = data[field]['content_words']
            tw_loss = otw - stw
            cw_loss = ocw - scw
            print(f"{label:<18} {fl:<14} {tw_loss:>10,} {pct(tw_loss, otw):>7.1f}% {cw_loss:>12,} {pct(cw_loss, ocw):>9.1f}%", file=out)

    # Table 3: Aggregate loss
    print("\n" + "=" * 90, file=out)
    print("TABLE 3: Aggregate Loss (all fields combined)", file=out)
    print("=" * 90, file=out)
    header3 = f"{'File':<18} {'Total Words':>12} {'Words Lost':>11} {'% Total':>8} {'Content':>10} {'Content Lost':>13} {'% Content':>10}"
    print(header3, file=out)
    print("-" * 90, file=out)

    oa = orig['_aggregate']
    print(f"{'original':<18} {oa['total_words']:>12,} {'—':>11} {'—':>8} {oa['content_words']:>10,} {'—':>13} {'—':>10}", file=out)
    for label, data in branch_results.items():
        a = data['_aggregate']
        tw_loss = oa['total_words'] - a['total_words']
        cw_loss = oa['content_words'] - a['content_words']
        print(f"{label:<18} {a['total_words']:>12,} {tw_loss:>11,} {pct(tw_loss, oa['total_words']):>7.1f}% {a['content_words']:>10,} {cw_loss:>13,} {pct(cw_loss, oa['content_words']):>9.1f}%", file=out)

    # Table 4: Per-record content loss distribution
    print("\n" + "=" * 90, file=out)
    print("TABLE 4: Per-Record Content Word Loss Distribution (combined fields)", file=out)
    print("=" * 90, file=out)
    header4 = f"{'File':<18} {'Mean':>6} {'Min':>6} {'P25':>6} {'Median':>7} {'P75':>6} {'P90':>6} {'P95':>6} {'Max':>6}"
    print(header4, file=out)
    print("-" * 90, file=out)

    # Combine per-record data across fields for each file
    orig_combined = []
    for i in range(orig[fields[0]]['record_count']):
        otw = sum(orig[f]['per_record'][i][0] for f in fields)
        ocw = sum(orig[f]['per_record'][i][1] for f in fields)
        orig_combined.append((otw, ocw))

    for label, data in branch_results.items():
        stripped_combined = []
        for i in range(data[fields[0]]['record_count']):
            stw = sum(data[f]['per_record'][i][0] for f in fields)
            scw = sum(data[f]['per_record'][i][1] for f in fields)
            stripped_combined.append((stw, scw))

        dist = compute_per_record_loss(orig_combined, stripped_combined)
        print(f"{label:<18} {dist['mean']:>5.1f}% {dist['min']:>5.1f}% {dist['p25']:>5.1f}% {dist['median']:>6.1f}% {dist['p75']:>5.1f}% {dist['p90']:>5.1f}% {dist['p95']:>5.1f}% {dist['max']:>5.1f}%", file=out)

    if args.output:
        out.close()
        print(f"\nResults written to {args.output}", file=sys.stderr)

    print("\nDone.", file=sys.stderr)


if __name__ == '__main__':
    main()
