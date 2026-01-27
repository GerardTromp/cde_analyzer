#
# File: actions/strip_discover/run.py
#
"""
Strip Discover - Run module for pattern discovery.

Discovers instrument patterns in CDE text fields using flexible regex matching.
Outputs a TSV file for curator review before stripping.
"""
import json
import re
from argparse import Namespace
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from utils.logger import logging
from utils.file_utils import exit_if_missing, graceful_interrupt
from pydantic import ValidationError
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
    if len(parts) >= 2:
        filepath = parts[0]
        column_name = parts[1]
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
                # Strip Excel's auto-added quotes around fields containing commas
                pattern = fields[col_idx].strip().strip('"')
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
    if len(parts) == 1:
        filepath = parts[0]
    elif len(parts) == 2:
        filepath, pattern_column = parts
    elif len(parts) >= 3:
        filepath = parts[0]
        pattern_column = parts[1]
        tinyids_column = parts[2]
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

            # Strip Excel's auto-added quotes around fields containing commas
            pattern = fields[pattern_idx].strip().strip('"')
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


def write_discovered_patterns_tsv(
    verbatim_map: Dict[str, Set[str]],
    output_path: str,
    pattern_type: str = "prefix",
    source_patterns: Optional[Dict[str, str]] = None
) -> None:
    """
    Write discovered patterns to TSV file.

    Args:
        verbatim_map: Dict mapping verbatim pattern -> set of tinyIds
        output_path: Path to output TSV file
        pattern_type: Type of patterns ('prefix' or 'bare')
        source_patterns: Optional mapping verbatim -> source pattern
    """
    # Sort by length descending for curator review
    sorted_patterns = sorted(verbatim_map.items(), key=lambda x: len(x[0]), reverse=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\ttype\tsource_pattern\n")
        for verbatim, tinyids in sorted_patterns:
            tinyids_str = " ".join(sorted(tinyids))
            source = source_patterns.get(verbatim, "") if source_patterns else ""
            f.write(f"{verbatim}\t{tinyids_str}\t{pattern_type}\t{source}\n")

    logger.info(f"Wrote {len(sorted_patterns)} discovered patterns to {output_path}")


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
    import re
    from collections import Counter

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


def extract_abbreviations_from_instruments(
    instruments_path: str,
    families_path: Optional[str] = None
) -> Set[str]:
    """
    Extract unique abbreviations from instruments.tsv and optionally instrument_families.tsv.

    Args:
        instruments_path: Path to instruments.tsv file.
        families_path: Optional path to instrument_families.tsv file.

    Returns:
        Set of unique abbreviation strings.
    """
    abbreviations = set()

    # Read instruments.tsv - look for 'acronym' column
    if Path(instruments_path).exists():
        with open(instruments_path, encoding="utf-8") as f:
            header_line = f.readline().strip()
            headers = [h.lower() for h in header_line.split('\t')]

            # Find acronym column
            acronym_idx = -1
            for i, h in enumerate(headers):
                if h == 'acronym':
                    acronym_idx = i
                    break

            if acronym_idx >= 0:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    fields = line.split('\t')
                    if acronym_idx < len(fields):
                        acronym = fields[acronym_idx].strip().strip('"')
                        if acronym and len(acronym) >= 2:
                            abbreviations.add(acronym)

        logger.info(f"Extracted {len(abbreviations)} abbreviations from {instruments_path}")

    # Read instrument_families.tsv if provided - look for 'all_acronyms' column
    if families_path and Path(families_path).exists():
        with open(families_path, encoding="utf-8") as f:
            header_line = f.readline().strip()
            headers = [h.lower() for h in header_line.split('\t')]

            # Find all_acronyms column
            all_acronyms_idx = -1
            for i, h in enumerate(headers):
                if h == 'all_acronyms':
                    all_acronyms_idx = i
                    break

            if all_acronyms_idx >= 0:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    fields = line.split('\t')
                    if all_acronyms_idx < len(fields):
                        acronyms_str = fields[all_acronyms_idx].strip().strip('"')
                        if acronyms_str:
                            # Split on pipe or comma
                            for acronym in re.split(r'[|,]', acronyms_str):
                                acronym = acronym.strip()
                                if acronym and len(acronym) >= 2:
                                    abbreviations.add(acronym)

            logger.info(f"Total abbreviations after families: {len(abbreviations)}")

    return abbreviations


def discover_abbreviation_patterns(
    json_path: str,
    abbreviations: Set[str],
    output_path: str,
    fields: List[str] = None
) -> Dict[str, Dict]:
    """
    Discover designation patterns that use known abbreviations.

    Finds two pattern types:
    1. [ABBREV] - bracketed suffix (e.g., "[PROMIS]", "[Neuro-QOL]")
    2. ABBREV -  - hyphen prefix (e.g., "PROMIS - Pain Interference...")

    Args:
        json_path: Path to CDE JSON file.
        abbreviations: Set of abbreviations to search for.
        output_path: Path to write output TSV.
        fields: Field paths to search (default: designations.*.designation)

    Returns:
        Dict mapping pattern -> {count, tinyIds, type}
    """
    from collections import defaultdict

    if fields is None:
        fields = ["designations.*.designation"]

    # Build regex patterns
    abbrev_list = sorted(abbreviations, key=len, reverse=True)  # Longest first
    abbrev_pattern = '|'.join(re.escape(a) for a in abbrev_list)

    # Pattern 1: [ABBREV] at end or anywhere
    bracketed_regex = re.compile(rf'\[({abbrev_pattern})\]', re.IGNORECASE)

    # Pattern 2: ABBREV -  at start of string
    hyphen_regex = re.compile(rf'^({abbrev_pattern})\s+-\s+', re.IGNORECASE)

    # Load JSON
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Track discovered patterns
    bracketed_patterns: Dict[str, Dict] = defaultdict(lambda: {'count': 0, 'tinyIds': set(), 'abbrev': ''})
    hyphen_patterns: Dict[str, Dict] = defaultdict(lambda: {'count': 0, 'tinyIds': set(), 'abbrev': ''})

    # Scan each record
    for item in data:
        tiny_id = item.get('tinyId', '')

        # Check designations
        for des_item in item.get('designations', []):
            designation = des_item.get('designation', '')
            if not designation:
                continue

            # Check for bracketed pattern
            match = bracketed_regex.search(designation)
            if match:
                bracketed_patterns[designation]['count'] += 1
                bracketed_patterns[designation]['tinyIds'].add(tiny_id)
                bracketed_patterns[designation]['abbrev'] = match.group(1)

            # Check for hyphen prefix pattern
            match = hyphen_regex.match(designation)
            if match:
                hyphen_patterns[designation]['count'] += 1
                hyphen_patterns[designation]['tinyIds'].add(tiny_id)
                hyphen_patterns[designation]['abbrev'] = match.group(1)

        # Also check definitions if in field list
        if "definitions.*.definition" in fields:
            for def_item in item.get('definitions', []):
                definition = def_item.get('definition', '')
                if not definition:
                    continue

                match = bracketed_regex.search(definition)
                if match:
                    bracketed_patterns[definition]['count'] += 1
                    bracketed_patterns[definition]['tinyIds'].add(tiny_id)
                    bracketed_patterns[definition]['abbrev'] = match.group(1)

                match = hyphen_regex.match(definition)
                if match:
                    hyphen_patterns[definition]['count'] += 1
                    hyphen_patterns[definition]['tinyIds'].add(tiny_id)
                    hyphen_patterns[definition]['abbrev'] = match.group(1)

    # Write output TSV
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\ttype\tabbreviation\tcount\n")

        # Write bracketed patterns (sorted by count descending)
        for pattern, info in sorted(bracketed_patterns.items(), key=lambda x: -x[1]['count']):
            tinyids_str = ' '.join(sorted(info['tinyIds']))
            f.write(f"{pattern}\t{tinyids_str}\t[ABBREV]\t{info['abbrev']}\t{info['count']}\n")

        # Write hyphen patterns (sorted by count descending)
        for pattern, info in sorted(hyphen_patterns.items(), key=lambda x: -x[1]['count']):
            tinyids_str = ' '.join(sorted(info['tinyIds']))
            f.write(f"{pattern}\t{tinyids_str}\tABBREV - \t{info['abbrev']}\t{info['count']}\n")

    # Summary by abbreviation
    abbrev_summary = defaultdict(lambda: {'bracketed': 0, 'hyphen': 0, 'tinyIds_b': set(), 'tinyIds_h': set()})
    for pattern, info in bracketed_patterns.items():
        abbrev_summary[info['abbrev']]['bracketed'] += 1
        abbrev_summary[info['abbrev']]['tinyIds_b'].update(info['tinyIds'])
    for pattern, info in hyphen_patterns.items():
        abbrev_summary[info['abbrev']]['hyphen'] += 1
        abbrev_summary[info['abbrev']]['tinyIds_h'].update(info['tinyIds'])

    logger.info(f"Wrote {len(bracketed_patterns) + len(hyphen_patterns)} patterns to {output_path}")

    return {
        'bracketed_patterns': dict(bracketed_patterns),
        'hyphen_patterns': dict(hyphen_patterns),
        'abbrev_summary': dict(abbrev_summary)
    }


def add_patterns_to_supplementary(
    curated_tsv_path: str,
    section_name: str = "added_patterns",
    delete_after: bool = True
) -> int:
    """
    Add patterns from curated TSV to supplementary_patterns.yaml.

    Args:
        curated_tsv_path: Path to curated TSV file with 'pattern', 'name' columns
        section_name: YAML section name for imported patterns
        delete_after: If True, delete the TSV file after successful import

    Returns:
        Number of patterns added
    """
    import os
    from utils.config_loader import get_config_dir

    config_path = get_config_dir() / "supplementary_patterns.yaml"
    if not config_path.exists():
        logger.error(f"supplementary_patterns.yaml not found at {config_path}")
        raise SystemExit(1)

    # Load existing YAML
    import yaml
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Parse curated TSV - only include rows where 'include' column is 'yes'
    patterns_to_add = []
    with open(curated_tsv_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = [h.lower() for h in header_line.split('\t')]

        # Find required columns
        try:
            pattern_idx = headers.index('pattern')
            name_idx = headers.index('suggested_name') if 'suggested_name' in headers else headers.index('name')
        except ValueError as e:
            logger.error(f"Required column not found: {e}")
            raise SystemExit(1)

        # Find optional columns
        acronym_idx = headers.index('acronym') if 'acronym' in headers else -1
        include_idx = headers.index('include') if 'include' in headers else -1

        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')

            # Check include flag if present
            # Strip Excel's auto-added quotes around fields containing commas
            if include_idx >= 0 and include_idx < len(fields):
                include_val = fields[include_idx].strip().strip('"').lower()
                if include_val not in ('yes', 'y', 'true', '1'):
                    continue

            if pattern_idx >= len(fields) or name_idx >= len(fields):
                continue

            pattern = fields[pattern_idx].strip().strip('"')
            name = fields[name_idx].strip().strip('"')

            if not pattern or not name:
                continue

            entry = {'pattern': pattern, 'name': name}

            if acronym_idx >= 0 and acronym_idx < len(fields):
                acronym = fields[acronym_idx].strip().strip('"')
                if acronym:
                    entry['acronym'] = acronym

            patterns_to_add.append(entry)

    if not patterns_to_add:
        logger.warning("No patterns marked for inclusion (set 'include' column to 'yes')")
        return 0

    # Add to config
    if section_name not in config:
        config[section_name] = []

    # Check for duplicates
    existing_patterns = set()
    for section in config.values():
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict) and 'pattern' in item:
                    existing_patterns.add(item['pattern'])

    added_count = 0
    for entry in patterns_to_add:
        if entry['pattern'] not in existing_patterns:
            config[section_name].append(entry)
            existing_patterns.add(entry['pattern'])
            added_count += 1
        else:
            logger.warning(f"Skipping duplicate pattern: {entry['pattern']}")

    # Write updated YAML
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(f"Added {added_count} patterns to {section_name} section")

    # Delete input file if requested
    if delete_after and added_count > 0:
        os.remove(curated_tsv_path)
        logger.info(f"Deleted curated file: {curated_tsv_path}")

    return added_count


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for strip_discover action."""

    # Check for add-to-supplementary mode first (standalone, doesn't need other args)
    add_to_supplementary = getattr(args, 'add_to_supplementary', None)
    if add_to_supplementary:
        section_name = getattr(args, 'supplementary_section', 'added_patterns')
        count = add_patterns_to_supplementary(
            add_to_supplementary,
            section_name=section_name,
            delete_after=True
        )
        print(f"Added {count} patterns to supplementary_patterns.yaml ({section_name} section)")
        if count > 0:
            print("Input file deleted. Re-run phrase_miner with --extract-supplementary to pick up new patterns.")
        return 0

    # Check for false-negative analysis mode (early exit)
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
        print(f"  2. Run: cde_analyzer strip_discover --add-to-supplementary {args.output}")
        return 0

    # Check for merge mode first (early exit)
    merge_patterns = getattr(args, 'merge_patterns', None)
    if merge_patterns:
        if not getattr(args, 'output', None):
            logger.error("--output is required for --merge-patterns")
            raise SystemExit(1)
        from utils.flexible_pattern_matcher import merge_verbatim_tsv

        pattern_column = getattr(args, 'merge_pattern_column', 'pattern')
        tinyids_column = getattr(args, 'merge_tinyids_column', 'tinyIds')

        logger.info(f"Merge mode: combining duplicate patterns in {merge_patterns}")
        stats = merge_verbatim_tsv(
            merge_patterns,
            args.output,
            pattern_column=pattern_column,
            tinyids_column=tinyids_column
        )

        print(f"Input:  {stats['input_rows']} rows")
        print(f"Output: {stats['output_rows']} unique patterns")
        print(f"Merged: {stats['merged_count']} duplicate patterns")
        print(f"Wrote:  {args.output}")
        return 0

    # Check for coalesce mode (early exit)
    coalesce_variants = getattr(args, 'coalesce_variants', None)
    if coalesce_variants:
        if not getattr(args, 'output', None):
            logger.error("--output is required for --coalesce-variants")
            raise SystemExit(1)
        from utils.flexible_pattern_matcher import coalesce_variants_tsv

        pattern_column = getattr(args, 'merge_pattern_column', 'pattern')
        tinyids_column = getattr(args, 'merge_tinyids_column', 'tinyIds')
        report_path = getattr(args, 'coalesce_report', None)

        logger.info(f"Coalesce mode: removing subsumed patterns from {coalesce_variants}")
        stats = coalesce_variants_tsv(
            coalesce_variants,
            args.output,
            pattern_column=pattern_column,
            tinyids_column=tinyids_column,
            report_path=report_path
        )

        print(f"\nCoalesce complete:")
        print(f"  Input:    {stats['input_patterns']} patterns")
        print(f"  Output:   {stats['output_patterns']} patterns")
        print(f"  Subsumed: {stats['subsumed_count']} patterns removed")
        if report_path:
            print(f"  Report:   {report_path}")
        print(f"  Wrote:    {args.output}")

        # Show a few examples of subsumptions
        if stats['subsumptions']:
            print(f"\nExample subsumptions (showing first 5):")
            for pattern, covers in stats['subsumptions'][:5]:
                cover_sample = covers[0][:40] if covers else "?"
                if len(covers) > 1:
                    cover_sample += f" (+{len(covers)-1} more)"
                print(f"  '{pattern[:50]}' ⊂ '{cover_sample}'")

        return 0

    # Check for discover-abbreviations mode (early exit)
    discover_abbrevs = getattr(args, 'discover_abbreviations', None)
    if discover_abbrevs:
        if not getattr(args, 'input', None):
            logger.error("--input is required for --discover-abbreviations")
            raise SystemExit(1)
        if not getattr(args, 'output', None):
            logger.error("--output is required for --discover-abbreviations")
            raise SystemExit(1)

        exit_if_missing(discover_abbrevs, "Instruments file")
        exit_if_missing(args.input, "Input JSON file")

        # Check for families file in same directory
        instruments_dir = Path(discover_abbrevs).parent
        families_path = instruments_dir / "instrument_families.tsv"
        if not families_path.exists():
            families_path = None

        logger.info(f"Extracting abbreviations from {discover_abbrevs}...")
        abbreviations = extract_abbreviations_from_instruments(
            discover_abbrevs,
            families_path=str(families_path) if families_path else None
        )

        if not abbreviations:
            logger.error("No abbreviations found in instruments file")
            raise SystemExit(1)

        logger.info(f"Scanning {args.input} for abbreviation-based patterns...")
        field_paths = getattr(args, 'fields', ["designations.*.designation"])
        results = discover_abbreviation_patterns(
            args.input,
            abbreviations,
            args.output,
            fields=field_paths
        )

        # Print summary
        n_bracketed = len(results['bracketed_patterns'])
        n_hyphen = len(results['hyphen_patterns'])
        total = n_bracketed + n_hyphen

        print(f"\nAbbreviation Pattern Discovery:")
        print(f"=" * 70)
        print(f"Abbreviations searched: {len(abbreviations)}")
        print(f"Patterns found:")
        print(f"  [ABBREV] suffix patterns: {n_bracketed}")
        print(f"  ABBREV -  prefix patterns: {n_hyphen}")
        print(f"  Total: {total}")

        # Summary by abbreviation
        if results['abbrev_summary']:
            print(f"\nBy abbreviation:")
            for abbrev, info in sorted(results['abbrev_summary'].items(),
                                        key=lambda x: -(x[1]['bracketed'] + x[1]['hyphen'])):
                if info['bracketed'] or info['hyphen']:
                    tinyids_count = len(info['tinyIds_b'] | info['tinyIds_h'])
                    print(f"  {abbrev}: [{abbrev}]={info['bracketed']}, {abbrev} - ={info['hyphen']} ({tinyids_count} tinyIds)")

        print(f"\nWrote: {args.output}")
        print(f"\nTo include these patterns in stripping:")
        print(f"  1. Review {args.output} and remove false positives")
        print(f"  2. Merge with your curated instruments.tsv")
        print(f"  3. Run strip_phrases with the merged pattern list")
        return 0

    # Check for analyze-conflicts mode (early exit)
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

    # Main discovery mode - requires --input, --model, --pattern-list, --output
    if not getattr(args, 'input', None):
        logger.error("--input is required for discovery mode")
        raise SystemExit(1)
    if not getattr(args, 'model', None):
        logger.error("--model is required for discovery mode")
        raise SystemExit(1)
    if not getattr(args, 'pattern_list', None):
        logger.error("--pattern-list is required for discovery mode")
        raise SystemExit(1)
    if not getattr(args, 'output', None):
        logger.error("--output is required for discovery mode")
        raise SystemExit(1)

    # Load patterns from pattern list
    expand_variants = getattr(args, 'expand_variants', False)
    include_name_only = getattr(args, 'include_name_only', True)
    use_expected_tinyids = getattr(args, 'use_expected_tinyids', False)

    try:
        patterns = load_pattern_list(
            args.pattern_list,
            expand_variants=expand_variants,
            include_name_only=include_name_only
        )
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Pattern list error: {e}")
        raise SystemExit(1)

    # Load additional pattern lists if specified
    additional_lists = getattr(args, 'additional_pattern_lists', None)
    if additional_lists:
        seen = set(patterns)
        for spec in additional_lists:
            try:
                additional_patterns = load_pattern_list(
                    spec,
                    expand_variants=expand_variants,
                    include_name_only=include_name_only
                )
                new_count = 0
                for p in additional_patterns:
                    if p not in seen:
                        patterns.append(p)
                        seen.add(p)
                        new_count += 1
                logger.info(f"Added {new_count} new patterns from {spec}")
            except (FileNotFoundError, ValueError) as e:
                logger.error(f"Additional pattern list error: {e}")
                raise SystemExit(1)

    # Load tinyIds if filtered mode requested
    pattern_to_expected_tinyids = None
    if use_expected_tinyids:
        logger.info("Loading pattern list with tinyIds for filtered discovery...")
        try:
            _, pattern_to_expected_tinyids = load_pattern_list_with_tinyids(
                args.pattern_list
            )
            n_with_tinyids = sum(1 for ids in pattern_to_expected_tinyids.values() if ids)
            logger.info(f"Loaded tinyIds for {n_with_tinyids}/{len(pattern_to_expected_tinyids)} patterns")
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Could not load tinyIds: {e}")
            logger.warning("Falling back to full scan mode")

    # Load and parse CDE data
    model_class = MODEL_REGISTRY[args.model]
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
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} CDE records")

    # Import discovery functions
    from logic.verbatim_discoverer import discover_verbatim_from_models, extract_texts_from_models
    from utils.flexible_pattern_matcher import (
        extract_bare_instrument_names,
        generate_prefixed_patterns,
        compile_flexible_patterns,
        discover_verbatim_occurrences,
    )

    field_paths = getattr(args, 'fields', ["definitions.*.definition", "designations.*.designation"])
    fails_output = getattr(args, 'discover_fails', None)
    discover_bare_names = getattr(args, 'discover_bare_names', False)
    n_workers = getattr(args, 'workers', 1)

    # Track source patterns for output
    source_patterns: Dict[str, str] = {}

    # Detect if input patterns have anchors or are bare names
    bare_name_pairs_from_input = extract_bare_instrument_names(patterns)
    input_has_anchors = len(bare_name_pairs_from_input) > 0

    verbatim_map: Dict[str, Set[str]] = {}
    bare_verbatim_map: Dict[str, Set[str]] = {}

    if input_has_anchors:
        # Input patterns have anchors (e.g., "as part of PHQ-9")
        # Phase 1: Discover prefixed patterns as-is
        logger.info(f"Phase 1: Discovering verbatim occurrences of {len(patterns)} anchor-prefixed patterns...")
        verbatim_map = discover_verbatim_from_models(
            parsed,
            patterns,
            field_paths,
            output_path=None,
            fails_output_path=fails_output,
            pattern_to_expected_tinyids=pattern_to_expected_tinyids,
            n_workers=n_workers
        )

        if not verbatim_map:
            logger.warning("No verbatim patterns discovered")

        # Phase 2: Discover bare names if requested
        if discover_bare_names and bare_name_pairs_from_input:
            logger.info("Phase 2: Discovering bare instrument names...")
            logger.info(f"Found {len(bare_name_pairs_from_input)} unique bare instrument names from input patterns")

            texts_with_ids = extract_texts_from_models(parsed, field_paths)
            bare_patterns = [bare_name for _, bare_name in bare_name_pairs_from_input]
            compiled_bare = compile_flexible_patterns(bare_patterns)

            bare_verbatim_map, _ = discover_verbatim_occurrences(
                texts_with_ids,
                compiled_bare,
                pattern_to_expected_tinyids=None,
                n_workers=n_workers
            )

            logger.info(f"Discovered {len(bare_verbatim_map)} bare name occurrences")

            # Track source patterns for bare names
            for orig_pattern, bare_name in bare_name_pairs_from_input:
                for verbatim in bare_verbatim_map:
                    if verbatim not in source_patterns:
                        if bare_name.lower() in verbatim.lower() or verbatim.lower() in bare_name.lower():
                            source_patterns[verbatim] = orig_pattern

    else:
        # Input patterns are bare names (e.g., "PHQ-9")
        # Need to swap approach: generate prefixed for Phase 1, use bare for Phase 2
        logger.info("Detected bare input patterns (no anchor prefixes)")

        if discover_bare_names:
            # Phase 1: Generate and discover prefixed patterns
            logger.info("Phase 1: Generating anchor-prefixed variants...")
            prefixed_pairs = generate_prefixed_patterns(patterns)

            if prefixed_pairs:
                prefixed_patterns = [prefixed for prefixed, _ in prefixed_pairs]
                logger.info(f"Discovering verbatim occurrences of {len(prefixed_patterns)} prefixed patterns...")

                verbatim_map = discover_verbatim_from_models(
                    parsed,
                    prefixed_patterns,
                    field_paths,
                    output_path=None,
                    fails_output_path=fails_output,
                    pattern_to_expected_tinyids=None,  # No filtering for generated patterns
                    n_workers=n_workers
                )

                # Track source (the bare name) for prefixed patterns
                for prefixed, bare_name in prefixed_pairs:
                    for verbatim in verbatim_map:
                        if verbatim not in source_patterns:
                            if bare_name.lower() in verbatim.lower():
                                source_patterns[verbatim] = bare_name

            if not verbatim_map:
                logger.info("No prefixed patterns discovered")

            # Phase 2: Discover bare patterns
            logger.info(f"Phase 2: Discovering bare occurrences of {len(patterns)} patterns...")
            texts_with_ids = extract_texts_from_models(parsed, field_paths)
            compiled_bare = compile_flexible_patterns(patterns)

            bare_verbatim_map, _ = discover_verbatim_occurrences(
                texts_with_ids,
                compiled_bare,
                pattern_to_expected_tinyids=pattern_to_expected_tinyids,
                n_workers=n_workers
            )

            logger.info(f"Discovered {len(bare_verbatim_map)} bare name occurrences")
        else:
            # No --discover-bare-names: just discover bare patterns as-is
            logger.info(f"Phase 1: Discovering verbatim occurrences of {len(patterns)} patterns...")
            # Note: These will be labeled as "prefix" in output for consistency,
            # but they're actually bare patterns matching wherever they appear
            verbatim_map = discover_verbatim_from_models(
                parsed,
                patterns,
                field_paths,
                output_path=None,
                fails_output_path=fails_output,
                pattern_to_expected_tinyids=pattern_to_expected_tinyids,
                n_workers=n_workers
            )

            if not verbatim_map:
                logger.warning("No verbatim patterns discovered")

    # Combine results and write output
    # Write prefixed patterns first, then bare names
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\ttype\tsource_pattern\n")

        # Write prefixed patterns (sorted by length descending)
        prefixed_sorted = sorted(verbatim_map.items(), key=lambda x: len(x[0]), reverse=True)
        for verbatim, tinyids in prefixed_sorted:
            tinyids_str = " ".join(sorted(tinyids))
            source = source_patterns.get(verbatim, "")
            f.write(f"{verbatim}\t{tinyids_str}\tprefix\t{source}\n")

        # Write bare name patterns (sorted by length descending)
        bare_sorted = sorted(bare_verbatim_map.items(), key=lambda x: len(x[0]), reverse=True)
        for verbatim, tinyids in bare_sorted:
            tinyids_str = " ".join(sorted(tinyids))
            source = source_patterns.get(verbatim, "")
            f.write(f"{verbatim}\t{tinyids_str}\tbare\t{source}\n")

    total_patterns = len(verbatim_map) + len(bare_verbatim_map)
    print(f"\nDiscovery complete:")
    print(f"  Input type: {'anchor-prefixed' if input_has_anchors else 'bare names'}")
    print(f"  Prefixed patterns: {len(verbatim_map)}")
    print(f"  Bare name patterns: {len(bare_verbatim_map)}")
    print(f"  Total: {total_patterns}")
    print(f"  Output: {args.output}")

    return 0
