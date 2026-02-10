#
# File: actions/strip_analyze/run.py
#
"""
Strip Analyze - Run module for pattern analysis.

Provides conflict analysis and false-negative analysis modes.
"""
import re
from argparse import Namespace
from collections import Counter
from typing import Dict, List, Optional

from utils.logger import logging
from utils.file_utils import exit_if_missing, graceful_interrupt
from utils.pattern_tsv_utils import load_pattern_list

logger = logging.getLogger(__name__)


def analyze_pattern_containment(
    patterns: List[str],
    output_path: Optional[str] = None,
    sort_order: str = "length"
) -> List[Dict]:
    """
    Analyze patterns for containment relationships that affect stripping order.

    Detects cases where:
    - Pattern A is a substring of Pattern B (containment)
    - Given the sort_order, A would be processed BEFORE B (actual conflict)
    - Stripping A first would prevent B from matching

    Args:
        patterns: List of patterns to analyze (in file order).
        output_path: Optional path to write TSV report.
        sort_order: How patterns will be sorted for processing:
                    - "length": longest-first (default) - only conflicts if short is longer
                    - "file": preserve input order - conflicts based on file position
                    - "alpha": alphabetical - conflicts based on alphabetical order

    Returns:
        List of conflict dictionaries with keys:
        - short_pattern: The contained (shorter) pattern
        - long_pattern: The containing (longer) pattern
        - relationship: 'prefix', 'suffix', or 'interior'
        - position: Character position where short appears in long
        - is_actual_conflict: True if short would be processed before long
        - recommendation: Suggested action for curator
    """
    conflicts = []

    # Build index mapping pattern -> file position
    pattern_file_order = {p: i for i, p in enumerate(patterns)}

    # Check all pairs for containment
    for short in patterns:
        if len(short) < 3:  # Skip very short patterns
            continue

        for long in patterns:
            if short == long or len(short) >= len(long):
                continue

            if short in long:
                # Determine relationship type
                pos = long.find(short)
                if pos == 0:
                    relationship = "prefix"
                elif pos + len(short) == len(long):
                    relationship = "suffix"
                else:
                    relationship = "interior"

                # Calculate what would remain if short is stripped from long
                remainder = long.replace(short, "", 1).strip()

                # Determine if this is an ACTUAL conflict based on sort order
                if sort_order == "length":
                    is_actual_conflict = False
                elif sort_order == "file":
                    short_pos = pattern_file_order.get(short, 0)
                    long_pos = pattern_file_order.get(long, 0)
                    is_actual_conflict = short_pos < long_pos
                else:  # alpha
                    is_actual_conflict = short < long

                # Determine recommendation
                if not is_actual_conflict:
                    recommendation = (
                        f"OK with --sort-order {sort_order}: longer pattern processed first."
                    )
                elif relationship == "prefix":
                    recommendation = (
                        f"CONFLICT: '{short[:30]}...' stripped first breaks '{long[:30]}...'. "
                        f"Reorder or use --sort-order length."
                    )
                elif relationship == "suffix":
                    recommendation = (
                        f"CONFLICT: '{short[:30]}...' stripped first breaks '{long[:30]}...'. "
                        f"Reorder or use --sort-order length."
                    )
                else:
                    recommendation = (
                        f"'{short[:30]}...' is interior to '{long[:30]}...'. "
                        f"Consider if you want to preserve surrounding text."
                    )

                conflicts.append({
                    "short_pattern": short,
                    "long_pattern": long,
                    "relationship": relationship,
                    "position": pos,
                    "remainder_if_short_stripped": remainder,
                    "is_actual_conflict": is_actual_conflict,
                    "recommendation": recommendation
                })

    # Write report if output path specified
    if output_path and conflicts:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("short_pattern\tlong_pattern\trelationship\tposition\tis_conflict\tremainder\trecommendation\n")
            for c in conflicts:
                f.write(
                    f"{c['short_pattern']}\t"
                    f"{c['long_pattern']}\t"
                    f"{c['relationship']}\t"
                    f"{c['position']}\t"
                    f"{'YES' if c['is_actual_conflict'] else 'no'}\t"
                    f"{c['remainder_if_short_stripped']}\t"
                    f"{c['recommendation']}\n"
                )
        actual_conflicts = sum(1 for c in conflicts if c['is_actual_conflict'])
        logger.info(
            f"Wrote {len(conflicts)} containment relationships to {output_path} "
            f"({actual_conflicts} actual conflicts with --sort-order {sort_order})"
        )

    return conflicts


def analyze_false_negatives(
    cleaned_json_path: str,
    output_path: str,
    anchor: str = "as part of"
) -> Dict[str, int]:
    """
    Analyze remaining anchor patterns in cleaned JSON to find false negatives.

    Args:
        cleaned_json_path: Path to cleaned JSON file (output from strip_phrases)
        output_path: Path to write TSV report
        anchor: Anchor phrase to search for (default: "as part of")

    Returns:
        Dict mapping pattern -> count
    """
    with open(cleaned_json_path, encoding="utf-8") as f:
        content = f.read()

    # Extract patterns after anchor, handling "the " optional prefix
    # Match: anchor + optional "the " + text until punctuation/quote/end
    pattern = re.compile(
        rf'{re.escape(anchor)}\s+(the\s+)?([^".,\n]+?)(?:[.,"]|\s*$)',
        re.IGNORECASE
    )

    counter = Counter()
    for match in pattern.finditer(content):
        # Don't include "the " prefix - supplementary patterns handle it optionally
        text = match.group(2).strip().rstrip('.,')
        if text:
            counter[text] += 1

    # Write TSV report with suggested canonical names
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("count\tpattern\tsuggested_name\tacronym\tinclude\n")
        for pattern_text, count in counter.most_common():
            # Generate suggested canonical name (title case, clean up)
            suggested = pattern_text.strip()
            # Extract acronym if present in parentheses
            acronym_match = re.search(r'\(([A-Z][A-Z0-9-]+)\)', suggested)
            acronym = acronym_match.group(1) if acronym_match else ""
            f.write(f"{count}\t{pattern_text}\t{suggested}\t{acronym}\tno\n")

    logger.info(f"Wrote {len(counter)} false-negative patterns to {output_path}")
    return dict(counter)


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for strip_analyze action."""

    # Check for false-negative analysis mode
    analyze_fn = getattr(args, 'analyze_false_negatives', False)
    if analyze_fn:
        if not getattr(args, 'input', None):
            logger.error("--input is required for --analyze-false-negatives")
            raise SystemExit(1)
        if not getattr(args, 'output', None):
            logger.error("--output is required for --analyze-false-negatives")
            raise SystemExit(1)
        anchor = getattr(args, 'fn_anchor', 'as part of')
        exit_if_missing(args.input, "Input JSON file")

        logger.info(f"Analyzing false negatives in {args.input}...")
        counter = analyze_false_negatives(args.input, args.output, anchor=anchor)

        # Print summary to terminal
        total_occurrences = sum(counter.values())
        print(f"\nFalse-Negative Analysis (anchor: '{anchor}'):")
        print(f"=" * 70)
        print(f"Total unique patterns: {len(counter)}")
        print(f"Total occurrences: {total_occurrences}")
        print(f"\nTop 20 by frequency:")
        for pattern, count in sorted(counter.items(), key=lambda x: -x[1])[:20]:
            print(f"  {count:4d}  {anchor} {pattern[:60]}")

        print(f"\nWrote report to: {args.output}")
        print(f"\nTo add patterns to supplementary_patterns.yaml:")
        print(f"  1. Edit {args.output} and set 'include' column to 'yes' for desired patterns")
        print(f"  2. Run: cde-analyzer pattern_util --add-to-supplementary {args.output}")
        return 0

    # Check for analyze-conflicts mode
    analyze_conflicts = getattr(args, 'analyze_conflicts', None)
    if analyze_conflicts:
        if not getattr(args, 'pattern_list', None):
            logger.error("--pattern-list is required for --analyze-conflicts")
            raise SystemExit(1)
        expand_variants = getattr(args, 'expand_variants', False)
        include_name_only = getattr(args, 'include_name_only', True)
        try:
            patterns = load_pattern_list(
                args.pattern_list,
                expand_variants=expand_variants,
                include_name_only=include_name_only
            )
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Pattern list error: {e}")
            raise SystemExit(1)

        sort_order = getattr(args, 'sort_order', 'length')
        logger.info(f"Analyzing {len(patterns)} patterns for containment conflicts (sort_order={sort_order})...")
        conflicts = analyze_pattern_containment(patterns, output_path=analyze_conflicts, sort_order=sort_order)

        # Print summary to console
        if conflicts:
            actual_conflicts = [c for c in conflicts if c['is_actual_conflict']]
            safe_containments = len(conflicts) - len(actual_conflicts)

            print(f"\nFound {len(conflicts)} containment relationships (--sort-order {sort_order}):")
            print(f"  Actual conflicts: {len(actual_conflicts)} (short pattern processed before long)")
            print(f"  Safe containments: {safe_containments} (long pattern processed first)")
            print(f"\nBy type:")
            print(f"  Prefix: {sum(1 for c in conflicts if c['relationship'] == 'prefix')}")
            print(f"  Suffix: {sum(1 for c in conflicts if c['relationship'] == 'suffix')}")
            print(f"  Interior: {sum(1 for c in conflicts if c['relationship'] == 'interior')}")
            print(f"\nWrote detailed report to: {analyze_conflicts}")

            if actual_conflicts:
                print("\nACTUAL CONFLICTS to review:")
                for c in actual_conflicts[:5]:
                    print(f"  [{c['relationship']:8}] '{c['short_pattern'][:40]}' in '{c['long_pattern'][:50]}'")
                if len(actual_conflicts) > 5:
                    print(f"  ... and {len(actual_conflicts) - 5} more (see report, filter is_conflict=YES)")
            else:
                print(f"\nNo ordering conflicts with --sort-order {sort_order}.")

            print(f"\nREVIEW RECOMMENDED: {len(conflicts)} containment relationships found.")
            print("  Some 'longer' patterns may represent sub-instruments worth preserving.")
            print(f"  Check report: {analyze_conflicts}")
        else:
            print("No containment relationships detected.")
        return 0

    # No mode specified
    logger.error("No mode specified. Use --analyze-conflicts or --analyze-false-negatives.")
    print("\nUsage:")
    print("  cde-analyzer strip_analyze --analyze-conflicts FILE -p PATTERN_LIST")
    print("  cde-analyzer strip_analyze --analyze-false-negatives -i CLEANED.json -o OUTPUT.tsv")
    raise SystemExit(1)
