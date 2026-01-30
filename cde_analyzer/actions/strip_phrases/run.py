#
# File: actions/strip_phrases/run.py
#
"""
Strip Phrases - Run module for phrase substitution.

Applies exact string replacement using pre-discovered patterns
from strip_discover or legacy phrase map files.
"""
import json
import re
from argparse import Namespace
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from utils.logger import logging
from utils.file_utils import exit_if_missing, graceful_interrupt
from pydantic import ValidationError
from logic.phrase_stripper import load_phrase_map, strip_phrases, set_trace_file, close_trace_file
from utils.diff_utils import print_json_diff
from utils.constants import MODEL_REGISTRY

logger = logging.getLogger(__name__)


def find_column_index(headers: List[str], column_name: str) -> int:
    """
    Find column index with case-insensitive matching.

    Args:
        headers: List of column header names from TSV file.
        column_name: Target column name to find.

    Returns:
        Index of the matching column.

    Raises:
        ValueError: If no matching column is found.
    """
    # Try exact match first
    if column_name in headers:
        return headers.index(column_name)

    # Try case-insensitive match
    column_lower = column_name.lower()
    for i, header in enumerate(headers):
        if header.lower() == column_lower:
            logger.debug(f"Column '{column_name}' matched as '{header}' (case-insensitive)")
            return i

    raise ValueError(f"Column '{column_name}' not found (case-insensitive)")


def load_discovered_patterns(
    spec: str,
    pattern_column: str = "pattern",
    tinyids_column: str = "tinyIds"
) -> List[Tuple[str, Optional[Set[str]], str]]:
    """
    Load discovered patterns from TSV file (output of strip_discover).

    Args:
        spec: File specification in format:
              - 'filename' (uses 'pattern' column, default tinyIds)
              - 'filename,column_name' (uses specified pattern column)
              - 'filename,pattern_column,tinyids_column' (explicit column names)
              Column matching is case-insensitive.
        pattern_column: Default column name for patterns (default: 'pattern').
        tinyids_column: Default column name for tinyIds (default: 'tinyIds').

    Returns:
        List of (pattern, tinyIds, replace_with) tuples in file order.
        tinyIds is a set of tinyId strings, or None if not specified.
        replace_with is the replacement string (default "" if no column present).

    Raises:
        FileNotFoundError: If the specified file doesn't exist.
        ValueError: If required columns are not found in the file.
    """
    # Parse spec: "file.tsv" or "file.tsv,column_name" or "file.tsv,pattern_col,tinyids_col"
    parts = spec.split(',')
    if len(parts) == 1:
        filepath = parts[0]
    elif len(parts) == 2:
        filepath = parts[0]
        pattern_column = parts[1]
    elif len(parts) >= 3:
        filepath = parts[0]
        pattern_column = parts[1]
        tinyids_column = parts[2]
    else:
        filepath = spec

    if not Path(filepath).exists():
        raise FileNotFoundError(f"Patterns file not found: {filepath}")

    patterns_list = []

    with open(filepath, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        try:
            pattern_idx = find_column_index(headers, pattern_column)
        except ValueError:
            raise ValueError(
                f"Pattern column '{pattern_column}' not found in {filepath}. "
                f"Available columns: {', '.join(headers)}"
            )

        # tinyIds column is optional
        tinyids_idx = None
        try:
            tinyids_idx = find_column_index(headers, tinyids_column)
        except ValueError:
            logger.debug(f"tinyIds column '{tinyids_column}' not found, applying to all records")

        # replace_with column is optional
        replace_idx = None
        try:
            replace_idx = find_column_index(headers, "replace_with")
        except ValueError:
            pass  # no replace_with column — default to ""

        if replace_idx is not None:
            logger.info("Found 'replace_with' column — using per-pattern replacements")

        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')
            if pattern_idx >= len(fields):
                continue

            # Strip Excel's auto-added quotes around fields containing commas
            pattern = fields[pattern_idx].strip().strip('"')
            if not pattern:
                continue

            # Parse tinyIds if column exists
            # Support both space-separated and pipe-separated formats (or mixed)
            tinyids = None
            if tinyids_idx is not None and tinyids_idx < len(fields):
                tinyids_str = fields[tinyids_idx].strip().strip('"')
                if tinyids_str:
                    # Split on whitespace or pipe, filter empty strings
                    tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)

            # Parse replace_with if column exists
            replace_with = ""
            if replace_idx is not None and replace_idx < len(fields):
                replace_with = fields[replace_idx].strip().strip('"')

            patterns_list.append((pattern, tinyids, replace_with))

    logger.info(f"Loaded {len(patterns_list)} patterns from {filepath}")
    return patterns_list


def patterns_to_phrase_map(
    patterns: List[Tuple[str, Optional[Set[str]], str]],
    field_paths: List[str],
    replace_with: str = "",
    sort_order: str = "length"
) -> List[Tuple[str, str, str, Optional[Set[str]]]]:
    """
    Convert a list of patterns to phrase_map format.

    Args:
        patterns: List of (pattern, tinyIds, replace_with) tuples.
        field_paths: List of field paths to apply stripping to.
        replace_with: Default replacement string (used when per-pattern
                      replace_with is empty). Default: empty string to remove.
        sort_order: Pattern ordering strategy:
                    - "length": longest-first (handles nested patterns)
                    - "file": preserve input order (curator control)
                    - "alpha": alphabetical (reproducibility)

    Returns:
        List of (path, phrase, replace, tinyIds) tuples.
    """
    # Order patterns according to specified strategy
    if sort_order == "length":
        sorted_patterns = sorted(patterns, key=lambda x: len(x[0]), reverse=True)
        order_desc = "longest-first"
    elif sort_order == "file":
        sorted_patterns = patterns  # preserve input order
        order_desc = "file order (curator-defined)"
    else:  # alpha
        sorted_patterns = sorted(patterns, key=lambda x: x[0])
        order_desc = "alphabetical"

    phrase_map = []
    has_per_pattern = any(len(p) > 2 and p[2] for p in sorted_patterns)
    for entry in sorted_patterns:
        pattern = entry[0]
        tinyids = entry[1]
        per_pattern_replace = entry[2] if len(entry) > 2 else ""
        # Use per-pattern replace_with if present, otherwise fall back to global
        effective_replace = per_pattern_replace if per_pattern_replace else replace_with
        for path in field_paths:
            phrase_map.append((path, pattern, effective_replace, tinyids))

    unique_patterns = len(set(p[0] for p in patterns))
    logger.info(f"Created phrase map: {unique_patterns} patterns x {len(field_paths)} paths = {len(phrase_map)} entries")
    logger.info(f"Pattern order: {order_desc}")
    if has_per_pattern:
        replace_count = sum(1 for p in patterns if len(p) > 2 and p[2])
        logger.info(f"Per-pattern replacements: {replace_count} patterns have custom replace_with values")
    return phrase_map


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for strip_phrases action."""

    model_class = MODEL_REGISTRY[args.model]

    # Load and parse CDE data
    input_path = exit_if_missing(args.input, "Input file")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            print(f"Error Type: {error['type']}")
            print(f"Message: {error['msg']}")
            print(f"Location: {error['loc']}")
            if "input" in error:
                print(f"Input: {error['input']}")
            if "ctx" in error:
                print(f"Context: {error['ctx']}")
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} CDE records")

    # Load phrase map from either --patterns or --phrases
    if args.patterns:
        # New discovered patterns mode
        try:
            patterns = load_discovered_patterns(args.patterns)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Patterns file error: {e}")
            raise SystemExit(1)

        # Diagnostic: summarize what was loaded
        patterns_with_tinyids = sum(1 for p in patterns if p[1] is not None)
        all_tinyids = set()
        for p in patterns:
            if p[1]:
                all_tinyids.update(p[1])
        logger.info(f"Patterns summary: {len(patterns)} total, {patterns_with_tinyids} with tinyId restrictions")
        logger.info(f"  Unique tinyIds referenced: {len(all_tinyids)}")
        if patterns:
            sample = patterns[0]
            sample_tids = len(sample[1]) if sample[1] else 0
            logger.info(f"  First pattern: '{sample[0][:50]}...' ({sample_tids} tinyIds)")

        # Check overlap between input tinyIds and pattern tinyIds
        input_tinyids = set(p.tinyId for p in parsed if hasattr(p, 'tinyId') and p.tinyId)
        overlap = all_tinyids & input_tinyids
        logger.info(f"  Input records: {len(input_tinyids)} unique tinyIds")
        logger.info(f"  Overlap with patterns: {len(overlap)} tinyIds")
        if len(overlap) == 0 and len(all_tinyids) > 0:
            logger.warning("NO OVERLAP: Pattern tinyIds don't match any input records!")
            logger.warning("  Patterns will not match anything. Consider removing tinyIds column.")

        # Deep diagnostic: sample an overlapping record and check if pattern exists in text
        if overlap:
            sample_tid = next(iter(overlap))
            logger.info(f"  DEBUG: Sampling overlapping tinyId '{sample_tid}'")
            # Find which pattern(s) reference this tinyId
            for pattern_text, tids, *_ in patterns:
                if tids and sample_tid in tids:
                    logger.info(f"    Pattern for this tinyId: '{pattern_text[:60]}'")
            # Find the record with this tinyId and check its text
            for p in parsed:
                if hasattr(p, 'tinyId') and p.tinyId == sample_tid:
                    # Check definitions
                    if hasattr(p, 'definitions') and p.definitions:
                        for d in p.definitions:
                            if hasattr(d, 'definition') and d.definition:
                                text_sample = d.definition[:100].replace('\n', ' ')
                                logger.info(f"    Definition text: '{text_sample}...'")
                    break

        field_paths = getattr(args, 'fields', ["definitions.*.definition", "designations.*.designation"])
        sort_order = getattr(args, 'sort_order', 'length')
        phrase_map = patterns_to_phrase_map(patterns, field_paths, sort_order=sort_order)

    else:
        # Legacy phrase map mode
        phrase_map = load_phrase_map(args.phrases)
        logger.info(f"Loaded {len(phrase_map)} phrase map entries from {args.phrases}")

    # Enable trace output if requested
    trace_file = getattr(args, 'trace_matching', None)
    if trace_file:
        set_trace_file(trace_file)
        logger.info(f"Writing matching trace to {trace_file}")

    # Apply phrase stripping
    n_workers = getattr(args, 'workers', 1)

    # Force sequential when trace is enabled (trace file handle not shared across processes)
    if trace_file and n_workers != 1:
        logger.warning(f"Trace enabled: forcing sequential processing (workers=1 instead of {n_workers})")
        n_workers = 1

    logger.info(f"Stripping phrases from {len(parsed)} records (workers={n_workers})...")
    cleaned = strip_phrases(parsed, phrase_map, n_workers=n_workers)
    logger.info("Phrase stripping complete")

    # Close trace file if open
    if trace_file:
        close_trace_file()
        logger.info(f"Trace file written to {trace_file}")

    # Write output
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        cleaned_json = [item.model_dump(mode="json") for item in cleaned]
        f.write(json.dumps(cleaned_json, indent=2))
    logger.info(f"Wrote cleaned output to {args.output}")

    # Optional remnant detection
    remnant_report = getattr(args, 'remnant_report', None)
    detect_remnants_flag = getattr(args, 'detect_remnants', False) or remnant_report
    if detect_remnants_flag:
        from logic.remnant_detector import detect_remnants, summarize_remnants, write_remnant_report, affected_records
        field_paths_for_remnants = getattr(args, 'fields', ["definitions.*.definition", "designations.*.designation"])
        remnants = detect_remnants(cleaned, field_paths_for_remnants)
        summary = summarize_remnants(remnants)
        logger.info(f"Remnant detection: {len(remnants)} artifacts in {affected_records(remnants)} records")
        for rtype, count in summary.items():
            logger.info(f"  {rtype}: {count}")
        if remnant_report:
            write_remnant_report(remnants, remnant_report)
            logger.info(f"Remnant report written to {remnant_report}")

    # Optional diff output
    if args.diff or args.diff_output or args.summary:
        original_json = [item.model_dump(mode="json") for item in parsed]
        cleaned_json = [item.model_dump(mode="json") for item in cleaned]
        original_json = json.dumps(original_json, indent=2)
        cleaned_json = json.dumps(cleaned_json, indent=2)

        print_json_diff(
            original=original_json,
            cleaned=cleaned_json,
            context=args.context,
            color=args.color,
            summary=args.summary,
            output_file=args.diff_output,
        )

    return 0
