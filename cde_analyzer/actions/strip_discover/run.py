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
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from utils.logger import logging
from utils.file_utils import exit_if_missing, graceful_interrupt
from utils.pattern_tsv_utils import load_pattern_list, load_pattern_list_with_tinyids
from pydantic import ValidationError
from utils.constants import MODEL_REGISTRY

logger = logging.getLogger(__name__)


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
    fields: List[str] = None,
    min_pattern_tinyids: int = 2
) -> Dict[str, Dict]:
    """
    Discover designation patterns that use known abbreviations.

    Finds two pattern types:
    1. [ABBREV] - bracketed suffix (e.g., "[PROMIS]", "[Neuro-QOL]")
    2. ABBREV -  - hyphen prefix (e.g., "PROMIS - Pain Interference...")

    For hyphen patterns, extracts common prefix patterns rather than full designations.
    Groups designations by abbreviation and finds longest common prefixes that meet
    the min_pattern_tinyids threshold.

    Args:
        json_path: Path to CDE JSON file.
        abbreviations: Set of abbreviations to search for.
        output_path: Path to write output TSV.
        fields: Field paths to search (default: designations.*.designation)
        min_pattern_tinyids: Minimum tinyIds for a prefix pattern to be output (default: 2)

    Returns:
        Dict mapping pattern -> {count, tinyIds, type}
    """
    if fields is None:
        fields = ["designations.*.designation"]

    # Build regex patterns
    abbrev_list = sorted(abbreviations, key=len, reverse=True)  # Longest first
    abbrev_pattern = '|'.join(re.escape(a) for a in abbrev_list)

    # Pattern 1: [ABBREV] at end or anywhere
    bracketed_regex = re.compile(rf'\[({abbrev_pattern})\]', re.IGNORECASE)

    # Pattern 2: ABBREV -  at start of string (capture the rest too)
    hyphen_regex = re.compile(rf'^({abbrev_pattern})\s+-\s+(.+)$', re.IGNORECASE)

    # Load JSON
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Track discovered patterns
    bracketed_patterns: Dict[str, Dict] = defaultdict(lambda: {'count': 0, 'tinyIds': set(), 'abbrev': ''})
    # For hyphen patterns, group by abbreviation first to find common prefixes
    hyphen_by_abbrev: Dict[str, List[Dict]] = defaultdict(list)

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

            # Check for hyphen prefix pattern - collect for prefix analysis
            match = hyphen_regex.match(designation)
            if match:
                abbrev = match.group(1)
                rest = match.group(2)  # Text after "ABBREV - "
                hyphen_by_abbrev[abbrev.upper()].append({
                    'full_text': designation,
                    'abbrev': abbrev,
                    'rest': rest,
                    'tinyId': tiny_id
                })

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
                    abbrev = match.group(1)
                    rest = match.group(2)
                    hyphen_by_abbrev[abbrev.upper()].append({
                        'full_text': definition,
                        'abbrev': abbrev,
                        'rest': rest,
                        'tinyId': tiny_id
                    })

    # Extract common prefix patterns from hyphen patterns
    hyphen_patterns: Dict[str, Dict] = {}

    for abbrev_key, items in hyphen_by_abbrev.items():
        if not items:
            continue

        # Get the canonical abbreviation form (from first item)
        canonical_abbrev = items[0]['abbrev']

        # Tokenize each "rest" portion and build prefix counts
        prefix_tinyids: Dict[str, set] = defaultdict(set)

        for item in items:
            rest = item['rest']
            tiny_id = item['tinyId']
            tokens = rest.split()

            # Build all prefixes from this designation
            for i in range(1, len(tokens) + 1):
                prefix = ' '.join(tokens[:i])
                prefix_tinyids[prefix].add(tiny_id)

        # Find longest prefixes that meet min_pattern_tinyids threshold
        # Sort by length descending, then by tinyId count descending
        sorted_prefixes = sorted(
            prefix_tinyids.items(),
            key=lambda x: (-len(x[0].split()), -len(x[1]))
        )

        # Greedy selection: pick longest prefixes that cover uncovered tinyIds
        covered_tinyids: set = set()
        selected_patterns = []

        for prefix, tinyids in sorted_prefixes:
            if len(tinyids) < min_pattern_tinyids:
                continue

            # Check if this prefix covers any new tinyIds
            new_tinyids = tinyids - covered_tinyids
            if new_tinyids:
                pattern = f"{canonical_abbrev} - {prefix}"
                selected_patterns.append({
                    'pattern': pattern,
                    'tinyIds': tinyids,
                    'abbrev': canonical_abbrev,
                    'count': len(tinyids)
                })
                covered_tinyids.update(tinyids)

        # Add selected patterns
        for p in selected_patterns:
            hyphen_patterns[p['pattern']] = {
                'count': p['count'],
                'tinyIds': p['tinyIds'],
                'abbrev': p['abbrev']
            }

        # Log uncovered items (singletons that don't meet threshold)
        all_tinyids = {item['tinyId'] for item in items}
        uncovered = all_tinyids - covered_tinyids
        if uncovered:
            logger.debug(f"{canonical_abbrev}: {len(uncovered)} tinyIds not covered by prefix patterns")

    # Write output TSV
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("pattern\ttinyIds\ttype\tabbreviation\tcount\n")

        # Write bracketed patterns (sorted by count descending)
        # Filter by min_pattern_tinyids
        for pattern, info in sorted(bracketed_patterns.items(), key=lambda x: -x[1]['count']):
            if len(info['tinyIds']) >= min_pattern_tinyids:
                tinyids_str = ' '.join(sorted(info['tinyIds']))
                f.write(f"{pattern}\t{tinyids_str}\t[ABBREV]\t{info['abbrev']}\t{info['count']}\n")

        # Write hyphen prefix patterns (sorted by count descending)
        for pattern, info in sorted(hyphen_patterns.items(), key=lambda x: -x[1]['count']):
            tinyids_str = ' '.join(sorted(info['tinyIds']))
            f.write(f"{pattern}\t{tinyids_str}\tABBREV - \t{info['abbrev']}\t{info['count']}\n")

    # Count output
    bracketed_count = sum(1 for info in bracketed_patterns.values() if len(info['tinyIds']) >= min_pattern_tinyids)
    logger.info(f"Wrote {bracketed_count + len(hyphen_patterns)} patterns to {output_path} "
                f"(min_tinyids={min_pattern_tinyids})")

    # Summary by abbreviation
    abbrev_summary = defaultdict(lambda: {'bracketed': 0, 'hyphen': 0, 'tinyIds_b': set(), 'tinyIds_h': set()})
    for pattern, info in bracketed_patterns.items():
        if len(info['tinyIds']) >= min_pattern_tinyids:
            abbrev_summary[info['abbrev']]['bracketed'] += 1
            abbrev_summary[info['abbrev']]['tinyIds_b'].update(info['tinyIds'])
    for pattern, info in hyphen_patterns.items():
        abbrev_summary[info['abbrev']]['hyphen'] += 1
        abbrev_summary[info['abbrev']]['tinyIds_h'].update(info['tinyIds'])

    return {
        'bracketed_patterns': {k: v for k, v in bracketed_patterns.items() if len(v['tinyIds']) >= min_pattern_tinyids},
        'hyphen_patterns': dict(hyphen_patterns),
        'abbrev_summary': dict(abbrev_summary)
    }


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for strip_discover action."""

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
        min_tinyids = getattr(args, 'min_pattern_tinyids', 2)
        results = discover_abbreviation_patterns(
            args.input,
            abbreviations,
            args.output,
            fields=field_paths,
            min_pattern_tinyids=min_tinyids
        )

        # Print summary
        n_bracketed = len(results['bracketed_patterns'])
        n_hyphen = len(results['hyphen_patterns'])
        total = n_bracketed + n_hyphen

        print(f"\nAbbreviation Pattern Discovery:")
        print(f"=" * 70)
        print(f"Abbreviations searched: {len(abbreviations)}")
        print(f"Min tinyIds filter: {min_tinyids}")
        print(f"Patterns found:")
        print(f"  [ABBREV] suffix patterns: {n_bracketed}")
        print(f"  ABBREV -  prefix patterns (common prefixes): {n_hyphen}")
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
