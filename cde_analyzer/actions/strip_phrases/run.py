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
from logic.phrase_stripper import (
    load_phrase_map, strip_phrases, set_trace_file, close_trace_file,
    init_match_log, write_match_log, close_match_log, get_match_log
)
from utils.diff_utils import print_json_diff
from utils.constants import MODEL_REGISTRY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Anchor expansion for cleaner stripping (prefixes and suffixes)
# ---------------------------------------------------------------------------
# Import from remnant_detector to keep anchor lists in sync
from logic.remnant_detector import ANCHOR_PHRASE_REMNANTS, TRAILING_SUFFIX_REMNANTS

# Built-in defaults (used as fallback if no config found)
DEFAULT_PREFIXES = [f"{anchor} " for anchor in ANCHOR_PHRASE_REMNANTS]
DEFAULT_SUFFIXES = [f" {suffix}" for suffix in TRAILING_SUFFIX_REMNANTS]


def load_anchor_expansions() -> Tuple[List[str], List[str]]:
    """
    Load anchor expansion configuration from YAML files.

    Loading priority (later extends earlier):
      1. Built-in defaults
      2. Global config: config/anchor_expansions.yaml
      3. Local override: ./anchor_expansions.yaml in working directory

    Returns:
        Tuple of (prefixes, suffixes) lists with leading/trailing spaces.
    """
    import os
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, using built-in defaults for anchor expansion")
        return DEFAULT_PREFIXES, DEFAULT_SUFFIXES

    prefixes = list(DEFAULT_PREFIXES)
    suffixes = list(DEFAULT_SUFFIXES)

    # Find config directory relative to this file
    this_dir = Path(__file__).parent.parent.parent  # actions/strip_phrases -> cde_analyzer
    global_config = this_dir / "config" / "anchor_expansions.yaml"
    local_config = Path.cwd() / "anchor_expansions.yaml"

    configs_loaded = []

    for config_path in [global_config, local_config]:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                if config:
                    # Extend (add to) existing lists
                    if 'prefixes' in config and config['prefixes']:
                        new_prefixes = [f"{p} " if not p.endswith(' ') else p
                                       for p in config['prefixes']]
                        # Add only new ones (avoid duplicates)
                        for p in new_prefixes:
                            if p not in prefixes:
                                prefixes.append(p)
                    if 'suffixes' in config and config['suffixes']:
                        new_suffixes = [f" {s}" if not s.startswith(' ') else s
                                       for s in config['suffixes']]
                        for s in new_suffixes:
                            if s not in suffixes:
                                suffixes.append(s)
                    configs_loaded.append(str(config_path))
            except Exception as e:
                logger.warning(f"Error loading {config_path}: {e}")

    if configs_loaded:
        logger.info(f"Loaded anchor expansions from: {', '.join(configs_loaded)}")
    else:
        logger.debug("Using built-in anchor expansion defaults")

    return prefixes, suffixes


def expand_patterns_with_anchors(
    patterns: List[Tuple[str, Optional[Set[str]], str]],
    anchor_prefixes: Optional[List[str]] = None,
    anchor_suffixes: Optional[List[str]] = None,
) -> List[Tuple[str, Optional[Set[str]], str, str]]:
    """
    Expand patterns with anchor prefixes and suffixes for cleaner stripping.

    For each base pattern, generates variants with:
      - prefix + pattern + suffix (all combinations)
      - prefix + pattern (no suffix)
      - pattern + suffix (no prefix)
      - pattern (bare)

    Expanded variants are sorted longest-first by the caller, so the most
    complete match wins (anchor context gets stripped along with the pattern).

    Args:
        patterns: List of (pattern, tinyIds, replace_with) tuples.
        anchor_prefixes: Optional list of prefixes (with trailing space).
                         Default: loaded from config files.
        anchor_suffixes: Optional list of suffixes (with leading space).
                         Default: loaded from config files.

    Returns:
        List of (pattern, tinyIds, replace_with, source_pattern) tuples.
        source_pattern indicates the original pattern (for logging).
    """
    # Load from config if not provided
    if anchor_prefixes is None or anchor_suffixes is None:
        loaded_prefixes, loaded_suffixes = load_anchor_expansions()
        if anchor_prefixes is None:
            anchor_prefixes = loaded_prefixes
        if anchor_suffixes is None:
            anchor_suffixes = loaded_suffixes

    # Normalize patterns: if a pattern ends with " -" (designation format
    # artifact like "Instrument (ACRONYM) -"), also generate a variant without
    # it so the bare instrument name matches in definitions.
    normalized = []
    n_dash_variants = 0
    for pattern, tinyids, replace_with in patterns:
        normalized.append((pattern, tinyids, replace_with))
        if pattern.endswith(" -"):
            trimmed = pattern[:-2]
            normalized.append((trimmed, tinyids, replace_with))
            n_dash_variants += 1
    if n_dash_variants:
        logger.info(
            f"Trailing-dash normalization: added {n_dash_variants} variants "
            f"(patterns ending with ' -')"
        )

    expanded = []
    seen = set()  # Avoid duplicate expanded patterns

    for pattern, tinyids, replace_with in normalized:
        source = pattern  # Track original for logging

        # Generate all combinations: prefix + pattern + suffix
        for prefix in anchor_prefixes:
            for suffix in anchor_suffixes:
                expanded_pattern = prefix + pattern + suffix
                if expanded_pattern not in seen:
                    seen.add(expanded_pattern)
                    expanded.append((expanded_pattern, tinyids, replace_with, source))

        # Generate prefix + pattern (no suffix)
        for prefix in anchor_prefixes:
            expanded_pattern = prefix + pattern
            if expanded_pattern not in seen:
                seen.add(expanded_pattern)
                expanded.append((expanded_pattern, tinyids, replace_with, source))

        # Generate pattern + suffix (no prefix)
        for suffix in anchor_suffixes:
            expanded_pattern = pattern + suffix
            if expanded_pattern not in seen:
                seen.add(expanded_pattern)
                expanded.append((expanded_pattern, tinyids, replace_with, source))

        # Include the bare pattern
        if pattern not in seen:
            seen.add(pattern)
            expanded.append((pattern, tinyids, replace_with, source))

    n_prefixes = len(anchor_prefixes)
    n_suffixes = len(anchor_suffixes)
    logger.info(
        f"Anchor expansion: {len(patterns)} base patterns -> "
        f"{len(expanded)} total ({n_prefixes} prefixes x {n_suffixes} suffixes + combinations)"
    )
    return expanded


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

            # Strip Excel's auto-added quotes around fields containing commas,
            # and un-double CSV-escaped internal quotes (""x"" -> "x")
            pattern = fields[pattern_idx].strip().strip('"').replace('""', '"')
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


def load_verbatim_strip_patterns() -> List[Tuple[str, Optional[Set[str]], str]]:
    """
    Load verbatim strip patterns from config files.

    These are pre-curated patterns that escape the discovery logic and should
    be stripped directly. Useful for building a reusable library of known
    patterns that recur across datasets.

    Loading priority (later extends earlier):
      1. Global config: config/verbatim_strip_patterns.yaml
      2. Local override: ./verbatim_strip_patterns.yaml

    Returns:
        List of (pattern, tinyIds, replace_with) tuples.
        tinyIds is always None (applies to all records).
    """
    try:
        from utils.config_loader import load_verbatim_strip_patterns as load_from_config
        raw_patterns = load_from_config()
    except ImportError as e:
        logger.warning(f"Config loader not available: {e}")
        return []

    if not raw_patterns:
        return []

    # Convert (pattern, replace_with) to (pattern, tinyIds, replace_with) format
    # tinyIds is None = applies to all records
    patterns = [(pattern, None, replace_with) for pattern, replace_with in raw_patterns]
    logger.info(f"Loaded {len(patterns)} verbatim strip patterns from config")
    return patterns


def merge_pattern_lists(
    *pattern_lists: List[Tuple[str, Optional[Set[str]], str]]
) -> List[Tuple[str, Optional[Set[str]], str]]:
    """
    Merge multiple pattern lists, deduplicating by pattern text.

    Later lists take precedence for duplicate patterns (replace_with value).

    Args:
        pattern_lists: Variable number of pattern lists to merge.

    Returns:
        Merged list of (pattern, tinyIds, replace_with) tuples.
    """
    seen = {}  # pattern_text -> (pattern, tinyIds, replace_with)

    for plist in pattern_lists:
        for pattern, tinyids, replace_with in plist:
            if pattern in seen:
                # Merge tinyIds (union) if both have them
                existing = seen[pattern]
                if existing[1] is not None and tinyids is not None:
                    merged_tids = existing[1] | tinyids
                elif tinyids is not None:
                    merged_tids = tinyids
                else:
                    merged_tids = existing[1]
                # Later replace_with takes precedence (unless empty)
                merged_replace = replace_with if replace_with else existing[2]
                seen[pattern] = (pattern, merged_tids, merged_replace)
            else:
                seen[pattern] = (pattern, tinyids, replace_with)

    merged = list(seen.values())
    logger.debug(f"Merged {sum(len(pl) for pl in pattern_lists)} patterns -> {len(merged)} unique")
    return merged


def patterns_to_phrase_map(
    patterns: List[Tuple],
    field_paths: List[str],
    replace_with: str = "",
    sort_order: str = "length"
) -> Tuple[List[Tuple[str, str, str, Optional[Set[str]]]], Dict[str, str]]:
    """
    Convert a list of patterns to phrase_map format.

    Args:
        patterns: List of tuples in one of two formats:
                  - (pattern, tinyIds, replace_with) - standard format
                  - (pattern, tinyIds, replace_with, source_pattern) - expanded format
        field_paths: List of field paths to apply stripping to.
        replace_with: Default replacement string (used when per-pattern
                      replace_with is empty). Default: empty string to remove.
        sort_order: Pattern ordering strategy:
                    - "length": longest-first (handles nested patterns)
                    - "file": preserve input order (curator control)
                    - "alpha": alphabetical (reproducibility)

    Returns:
        Tuple of:
        - List of (path, phrase, replace, tinyIds) tuples.
        - Dict mapping expanded pattern -> source pattern (for logging).
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
    source_map = {}  # Maps expanded pattern -> source pattern for logging
    has_per_pattern = any(len(p) > 2 and p[2] for p in sorted_patterns)

    for entry in sorted_patterns:
        pattern = entry[0]
        tinyids = entry[1]
        per_pattern_replace = entry[2] if len(entry) > 2 else ""
        # Track source pattern if present (4th element from expansion)
        source_pattern = entry[3] if len(entry) > 3 else pattern
        source_map[pattern] = source_pattern

        # Use per-pattern replace_with if present, otherwise fall back to global
        effective_replace = per_pattern_replace if per_pattern_replace else replace_with
        for path in field_paths:
            phrase_map.append((path, pattern, effective_replace, tinyids))

    unique_patterns = len(set(p[0] for p in patterns))
    unique_sources = len(set(source_map.values()))
    logger.info(f"Created phrase map: {unique_patterns} patterns x {len(field_paths)} paths = {len(phrase_map)} entries")
    if unique_sources < unique_patterns:
        logger.info(f"  ({unique_sources} base patterns with anchor expansions)")
    logger.info(f"Pattern order: {order_desc}")
    if has_per_pattern:
        replace_count = sum(1 for p in patterns if len(p) > 2 and p[2])
        logger.info(f"Per-pattern replacements: {replace_count} patterns have custom replace_with values")

    return phrase_map, source_map


def write_match_summary(match_log: list, filepath: str):
    """
    Write aggregated pattern match summary as TSV.

    Args:
        match_log: List of match log entries from get_match_log().
        filepath: Output TSV file path.

    Output columns:
        - source_pattern: The base pattern (before anchor expansion)
        - match_count: Number of times this pattern was matched
        - unique_records: Number of unique tinyIds affected
    """
    from collections import Counter

    if not match_log:
        logger.warning("No match log entries to summarize")
        return

    # Aggregate by source_pattern
    pattern_counts = Counter()
    pattern_tinyids = {}  # source_pattern -> set of tinyIds

    for entry in match_log:
        source = entry.get('source_pattern', entry.get('matched_pattern', ''))
        tinyid = entry.get('tinyId', '')

        pattern_counts[source] += 1

        if source not in pattern_tinyids:
            pattern_tinyids[source] = set()
        if tinyid:
            pattern_tinyids[source].add(tinyid)

    # Sort by count descending
    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])

    import csv
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['source_pattern', 'match_count', 'unique_records'])
        for pattern, count in sorted_patterns:
            unique_count = len(pattern_tinyids.get(pattern, set()))
            writer.writerow([pattern, count, unique_count])

    logger.info(f"Wrote match summary: {len(sorted_patterns)} patterns to {filepath}")


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

        # Merge verbatim strip patterns from config (default: enabled)
        use_verbatim = getattr(args, 'verbatim_patterns', True)
        if use_verbatim:
            verbatim = load_verbatim_strip_patterns()
            if verbatim:
                original_count = len(patterns)
                patterns = merge_pattern_lists(patterns, verbatim)
                added = len(patterns) - original_count
                if added > 0:
                    logger.info(f"Added {added} new patterns from verbatim config")

        # Optional anchor expansion (default: enabled)
        expand_anchors = getattr(args, 'expand_anchors', True)
        if expand_anchors:
            patterns = expand_patterns_with_anchors(patterns)

        phrase_map, source_map = patterns_to_phrase_map(patterns, field_paths, sort_order=sort_order)

    else:
        # Legacy phrase map mode
        phrase_map = load_phrase_map(args.phrases)
        source_map = {}  # No source tracking for legacy mode
        logger.info(f"Loaded {len(phrase_map)} phrase map entries from {args.phrases}")

    # Enable trace output if requested
    trace_file = getattr(args, 'trace_matching', None)
    if trace_file:
        set_trace_file(trace_file)
        logger.info(f"Writing matching trace to {trace_file}")

    # Enable match log if requested (full audit trail or summary)
    match_log_file = getattr(args, 'match_log', None)
    match_summary_file = getattr(args, 'match_summary', None)
    logging_enabled = match_log_file or match_summary_file
    if logging_enabled:
        init_match_log(source_map)
        if match_log_file:
            logger.info(f"Match logging enabled -> {match_log_file}")
        if match_summary_file:
            logger.info(f"Match summary enabled -> {match_summary_file}")

    # Apply phrase stripping
    n_workers = getattr(args, 'workers', 1)

    # Force sequential only for trace file (writes to single file, can't parallelize)
    # Match logging now supports parallel execution with per-worker aggregation
    if trace_file and n_workers != 1:
        logger.warning(f"Trace file enabled: forcing sequential processing (workers=1 instead of {n_workers})")
        n_workers = 1

    logger.info(f"Stripping phrases from {len(parsed)} records (workers={n_workers})...")
    cleaned = strip_phrases(
        parsed, phrase_map, n_workers=n_workers,
        source_map=source_map, logging_enabled=logging_enabled
    )
    logger.info("Phrase stripping complete")

    # Close trace file if open
    if trace_file:
        close_trace_file()
        logger.info(f"Trace file written to {trace_file}")

    # Write match log and/or summary if enabled
    if logging_enabled:
        match_log_data = get_match_log()
        if match_log_file:
            write_match_log(match_log_file)
        if match_summary_file:
            write_match_summary(match_log_data, match_summary_file)
        close_match_log()

    # Convert to JSON dicts for output
    cleaned_json = [item.model_dump(mode="json") for item in cleaned]

    # Optional post-strip cleanup
    clean_remnants_flag = getattr(args, 'clean_remnants', False)
    if clean_remnants_flag:
        from logic.remnant_detector import clean_records
        field_paths_for_clean = getattr(args, 'fields', ["definitions.*.definition", "designations.*.designation"])
        modified = clean_records(cleaned_json, field_paths_for_clean)
        logger.info(f"Post-strip cleanup: {modified} fields cleaned")

    # Write output
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(cleaned_json, indent=2))
    logger.info(f"Wrote cleaned output to {args.output}")

    # Optional remnant detection (runs after cleanup if both are enabled)
    remnant_report = getattr(args, 'remnant_report', None)
    detect_remnants_flag = getattr(args, 'detect_remnants', False) or remnant_report
    if detect_remnants_flag:
        from logic.remnant_detector import detect_remnants_from_json, summarize_remnants, write_remnant_report, affected_records
        field_paths_for_remnants = getattr(args, 'fields', ["definitions.*.definition", "designations.*.designation"])
        remnants = detect_remnants_from_json(cleaned_json, field_paths_for_remnants)
        summary = summarize_remnants(remnants)
        logger.info(f"Remnant detection: {len(remnants)} artifacts in {affected_records(remnants)} records")
        for rtype, count in summary.items():
            logger.info(f"  {rtype}: {count}")
        if remnant_report:
            write_remnant_report(remnants, remnant_report)
            logger.info(f"Remnant report written to {remnant_report}")

    # Optional diff output
    if args.diff or args.diff_output or args.summary:
        original_json = json.dumps([item.model_dump(mode="json") for item in parsed], indent=2)
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
