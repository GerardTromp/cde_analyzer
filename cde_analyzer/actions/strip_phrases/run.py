#
# File: actions/strip_phrases/run.py
#
"""
Strip Phrases - Run module for phrase substitution.

Applies exact string replacement using pre-discovered patterns
from strip_discover or legacy phrase map files.
"""
import json
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
    filepath: str,
    pattern_column: str = "pattern",
    tinyids_column: str = "tinyIds"
) -> List[Tuple[str, Optional[Set[str]]]]:
    """
    Load discovered patterns from TSV file (output of strip_discover).

    Args:
        filepath: Path to discovered patterns TSV file.
        pattern_column: Column name for patterns (default: 'pattern').
        tinyids_column: Column name for tinyIds (default: 'tinyIds').

    Returns:
        List of (pattern, tinyIds) tuples in file order.
        tinyIds is a set of tinyId strings, or None if not specified.

    Raises:
        FileNotFoundError: If the specified file doesn't exist.
        ValueError: If required columns are not found in the file.
    """
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

        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')
            if pattern_idx >= len(fields):
                continue

            pattern = fields[pattern_idx].strip()
            if not pattern:
                continue

            # Parse tinyIds if column exists
            tinyids = None
            if tinyids_idx is not None and tinyids_idx < len(fields):
                tinyids_str = fields[tinyids_idx].strip()
                if tinyids_str:
                    tinyids = set(tinyids_str.split())

            patterns_list.append((pattern, tinyids))

    logger.info(f"Loaded {len(patterns_list)} patterns from {filepath}")
    return patterns_list


def patterns_to_phrase_map(
    patterns: List[Tuple[str, Optional[Set[str]]]],
    field_paths: List[str],
    replace_with: str = "",
    sort_order: str = "length"
) -> List[Tuple[str, str, str, Optional[Set[str]]]]:
    """
    Convert a list of patterns to phrase_map format.

    Args:
        patterns: List of (pattern, tinyIds) tuples.
        field_paths: List of field paths to apply stripping to.
        replace_with: Replacement string (default: empty string to remove).
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
    for pattern, tinyids in sorted_patterns:
        for path in field_paths:
            phrase_map.append((path, pattern, replace_with, tinyids))

    unique_patterns = len(set(p for p, _ in patterns))
    logger.info(f"Created phrase map: {unique_patterns} patterns x {len(field_paths)} paths = {len(phrase_map)} entries")
    logger.info(f"Pattern order: {order_desc}")
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
