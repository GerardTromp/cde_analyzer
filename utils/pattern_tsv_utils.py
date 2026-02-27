#
# File: utils/pattern_tsv_utils.py
#
"""
Shared TSV utilities for pattern loading and column manipulation.

Used by strip_discover, strip_analyze, and pattern_util actions.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from utils.logger import logging

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


def find_column_name(headers: List[str], column_name: str) -> str:
    """
    Find actual column header name with case-insensitive matching.

    Like find_column_index but returns the header string itself,
    useful with csv.DictReader where you need the exact key.

    Args:
        headers: List of column header names from TSV file.
        column_name: Target column name to find.

    Returns:
        The actual header string that matched.

    Raises:
        ValueError: If no matching column is found.
    """
    if column_name in headers:
        return column_name

    column_lower = column_name.lower()
    for header in headers:
        if header.lower() == column_lower:
            logger.debug(f"Column '{column_name}' matched as '{header}' (case-insensitive)")
            return header

    raise ValueError(f"Column '{column_name}' not found (case-insensitive)")


def load_pattern_list(
    spec: str,
    expand_variants: bool = False,
    include_name_only: bool = True,
    preserve_order: bool = False
) -> List[str]:
    """
    Load patterns from a TSV file.

    Args:
        spec: File specification in format:
              - 'filename' (uses 'full_match' column)
              - 'filename,column_name'
              - 'filename,column_name,tinyids_col' (third element ignored here)
              Column matching is case-insensitive.
        expand_variants: If True, generate spelling/punctuation variants.
        include_name_only: When expanding variants, include bare instrument names.
        preserve_order: If True, return patterns in file order (as list).
                        If False, return deduplicated patterns (order not guaranteed).

    Returns:
        List of pattern strings (preserves order, duplicates removed).

    Raises:
        FileNotFoundError: If the specified file doesn't exist.
        ValueError: If the specified column is not found in the file.
    """
    # Parse spec: "file.tsv" or "file.tsv,column_name" or "file.tsv,column_name,tinyids_col"
    parts = spec.split(',')
    explicit_column = False
    if len(parts) >= 2:
        filepath = parts[0]
        column_name = parts[1]
        explicit_column = True
    else:
        filepath = spec
        column_name = "full_match"

    if not Path(filepath).exists():
        raise FileNotFoundError(f"Pattern list file not found: {filepath}")

    # Use list to preserve order, track seen patterns to avoid duplicates
    patterns_list = []
    seen = set()

    with open(filepath, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        try:
            col_idx = find_column_index(headers, column_name)
        except ValueError:
            # Try fallback column names only if no explicit column was specified
            if not explicit_column:
                # Standard fallbacks: full_match → pattern
                fallback_names = ["pattern"] if column_name == "full_match" else []
                for fallback in fallback_names:
                    try:
                        col_idx = find_column_index(headers, fallback)
                        logger.info(f"Column '{column_name}' not found, using fallback '{fallback}'")
                        column_name = fallback
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(
                        f"Column '{column_name}' not found in {filepath}. "
                        f"Available columns: {', '.join(headers)}"
                    )
            else:
                raise ValueError(
                    f"Column '{column_name}' not found in {filepath}. "
                    f"Available columns: {', '.join(headers)}"
                )

        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')
            if col_idx < len(fields):
                # Strip Excel's auto-added quotes around fields containing commas,
                # and un-double CSV-escaped internal quotes (""x"" -> "x")
                pattern = fields[col_idx].strip().strip('"').replace('""', '"')
                if pattern and pattern not in seen:
                    patterns_list.append(pattern)
                    seen.add(pattern)

    logger.info(f"Loaded {len(patterns_list)} base patterns from {filepath} (column: {column_name})")

    # Optionally expand variants
    if expand_variants:
        from utils.pattern_variant_generator import expand_pattern_set
        expanded = expand_pattern_set(
            set(patterns_list),
            include_name_only=include_name_only,
            collect_acronyms=True,
            add_prefixes=True
        )
        logger.info(f"Expanded to {len(expanded)} patterns with variants")
        return list(expanded)

    return patterns_list


def load_pattern_list_with_tinyids(
    spec: str,
    pattern_column: str = "full_match",
    tinyids_column: str = "tinyIds"
) -> Tuple[List[str], Dict[str, Set[str]]]:
    """
    Load patterns with their expected tinyIds from a TSV file.

    This is used for filtered discovery mode, where each pattern is only
    searched in the texts from its expected tinyIds.

    Args:
        spec: File specification in format:
              - 'filename' (uses defaults: 'full_match' and 'tinyIds')
              - 'filename,pattern_column' (uses specified pattern column, default tinyIds)
              - 'filename,pattern_column,tinyids_column' (explicit column names)
              Column matching is case-insensitive.
        pattern_column: Default column name for patterns (default: 'full_match').
        tinyids_column: Default column name for tinyIds (default: 'tinyIds').

    Returns:
        Tuple of:
        - List of pattern strings (deduplicated, order preserved)
        - Dict mapping pattern -> set of expected tinyIds

    Raises:
        FileNotFoundError: If the specified file doesn't exist.
        ValueError: If required columns are not found in the file.
    """
    # Parse spec
    parts = spec.split(',')
    explicit_pattern_column = False
    if len(parts) == 1:
        filepath = parts[0]
    elif len(parts) == 2:
        filepath, pattern_column = parts
        explicit_pattern_column = True
    elif len(parts) >= 3:
        filepath = parts[0]
        pattern_column = parts[1]
        tinyids_column = parts[2]
        explicit_pattern_column = True
    else:
        filepath = spec

    if not Path(filepath).exists():
        raise FileNotFoundError(f"Pattern list file not found: {filepath}")

    patterns_list = []
    pattern_to_tinyids: Dict[str, Set[str]] = {}
    seen = set()

    with open(filepath, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        try:
            pattern_idx = find_column_index(headers, pattern_column)
        except ValueError:
            # Try fallback column names only if no explicit column was specified
            if not explicit_pattern_column:
                fallback_names = ["pattern"] if pattern_column == "full_match" else []
                for fallback in fallback_names:
                    try:
                        pattern_idx = find_column_index(headers, fallback)
                        logger.info(f"Pattern column '{pattern_column}' not found, using fallback '{fallback}'")
                        pattern_column = fallback
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(
                        f"Pattern column '{pattern_column}' not found in {filepath}. "
                        f"Available columns: {', '.join(headers)}"
                    )
            else:
                raise ValueError(
                    f"Pattern column '{pattern_column}' not found in {filepath}. "
                    f"Available columns: {', '.join(headers)}"
                )

        # tinyIds column is optional
        tinyids_idx = None
        try:
            tinyids_idx = find_column_index(headers, tinyids_column)
        except ValueError:
            logger.debug(f"tinyIds column '{tinyids_column}' not found, proceeding without filtering")

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
            tinyids = set()
            if tinyids_idx is not None and tinyids_idx < len(fields):
                tinyids_str = fields[tinyids_idx].strip().strip('"')
                if tinyids_str:
                    tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)

            # Add to list (dedup) and update tinyIds mapping
            if pattern not in seen:
                patterns_list.append(pattern)
                seen.add(pattern)
                pattern_to_tinyids[pattern] = tinyids
            else:
                # Merge tinyIds if pattern already seen
                pattern_to_tinyids[pattern].update(tinyids)

    has_tinyids = tinyids_idx is not None
    logger.info(
        f"Loaded {len(patterns_list)} patterns from {filepath} "
        f"(tinyIds: {'yes' if has_tinyids else 'no'})"
    )

    return patterns_list, pattern_to_tinyids


def load_parent_mapping(
    spec: str,
    pattern_column: str,
    parent_column: str,
    tinyids_column: str = "tinyids"
) -> Tuple[Dict[str, str], Dict[str, int]]:
    """
    Load parent phrase mapping and aggregated parent tinyId counts from a TSV.

    For each pattern (verbatim), maps it to its parent (generic) phrase.
    Aggregates tinyIds across all verbatim variants sharing the same parent
    to compute parent_tinyid_count.

    Args:
        spec: File spec (just the filepath portion, or 'file,col' format).
        pattern_column: Column with the pattern (e.g., 'verbatim_text').
        parent_column: Column with the parent phrase (e.g., 'lemma_text').
        tinyids_column: Column with tinyIds for aggregation.

    Returns:
        Tuple of:
        - Dict mapping pattern -> parent phrase
        - Dict mapping parent phrase -> total unique tinyId count
    """
    # Parse filepath from spec
    parts = spec.split(',')
    filepath = parts[0]

    if not Path(filepath).exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    pattern_to_parent: Dict[str, str] = {}
    parent_to_tinyids: Dict[str, Set[str]] = {}

    with open(filepath, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        pattern_idx = find_column_index(headers, pattern_column)
        parent_idx = find_column_index(headers, parent_column)

        tinyids_idx = None
        try:
            tinyids_idx = find_column_index(headers, tinyids_column)
        except ValueError:
            logger.debug(f"tinyIds column '{tinyids_column}' not found in parent mapping")

        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')
            if pattern_idx >= len(fields) or parent_idx >= len(fields):
                continue

            pattern = fields[pattern_idx].strip().strip('"').replace('""', '"')
            parent = fields[parent_idx].strip().strip('"').replace('""', '"')
            if not pattern or not parent:
                continue

            pattern_to_parent[pattern] = parent

            # Aggregate tinyIds by parent
            if parent not in parent_to_tinyids:
                parent_to_tinyids[parent] = set()
            if tinyids_idx is not None and tinyids_idx < len(fields):
                tinyids_str = fields[tinyids_idx].strip().strip('"')
                if tinyids_str:
                    parent_to_tinyids[parent].update(
                        t for t in re.split(r'[\s|]+', tinyids_str) if t
                    )

    # Convert to counts
    parent_to_count: Dict[str, int] = {
        parent: len(tids) for parent, tids in parent_to_tinyids.items()
    }

    logger.info(
        f"Loaded parent mapping: {len(pattern_to_parent)} patterns → "
        f"{len(parent_to_count)} parents from {filepath}"
    )

    return pattern_to_parent, parent_to_count
