#
# File: logic/verbatim_discoverer.py
#
"""
Verbatim phrase discovery for efficient stripping.

Two-phase approach:
1. Discovery: Use flexible regex to find actual verbatim occurrences
2. Substitution: Use exact string replacement on discovered phrases

This approach solves:
- Pattern ordering issues (no longer pattern-dependent)
- Orphan phrase fragments (only matched text is removed)
- Performance (targeted substitution per tinyId)
"""

import logging
from typing import List, Dict, Set, Tuple, Optional
from pathlib import Path
from pydantic import BaseModel

from utils.flexible_pattern_matcher import (
    compile_flexible_patterns,
    discover_verbatim_occurrences,
    write_verbatim_tsv,
    write_failed_patterns_tsv,
    load_verbatim_tsv
)

logger = logging.getLogger(__name__)


def extract_texts_from_models(
    model_list: List[BaseModel],
    field_paths: List[str]
) -> List[Tuple[str, str, str]]:
    """
    Extract text content from models at specified field paths.

    Args:
        model_list: List of Pydantic models
        field_paths: Field paths like "definitions.*.definition"

    Returns:
        List of (tinyId, field_path, text) tuples
    """
    results = []

    for model in model_list:
        tiny_id = getattr(model, 'tinyId', None)
        if not tiny_id:
            continue

        model_dict = model.model_dump(mode="python")

        for field_path in field_paths:
            texts = _extract_at_path(model_dict, field_path.split('.'))
            for text in texts:
                if text and isinstance(text, str):
                    results.append((tiny_id, field_path, text))

    logger.info(f"Extracted {len(results)} text spans from {len(model_list)} models")
    return results


def _extract_at_path(obj: any, parts: List[str]) -> List[str]:
    """
    Extract values at a dotted path with wildcard support.

    Args:
        obj: Current object (dict or list)
        parts: Remaining path parts

    Returns:
        List of string values found at path
    """
    if not parts:
        if isinstance(obj, str):
            return [obj]
        return []

    key = parts[0]
    rest = parts[1:]

    results = []

    if key == '*':
        if isinstance(obj, list):
            for item in obj:
                results.extend(_extract_at_path(item, rest))
    elif isinstance(obj, dict):
        if key in obj:
            results.extend(_extract_at_path(obj[key], rest))
    elif isinstance(obj, list):
        try:
            idx = int(key)
            if 0 <= idx < len(obj):
                results.extend(_extract_at_path(obj[idx], rest))
        except ValueError:
            pass

    return results


def discover_verbatim_from_models(
    model_list: List[BaseModel],
    source_patterns: List[str],
    field_paths: List[str],
    output_path: Optional[str] = None,
    fails_output_path: Optional[str] = None,
    pattern_to_expected_tinyids: Optional[Dict[str, Set[str]]] = None,
    n_workers: int = 1,
    allow_abbrev_variants: bool = False,
    allow_embedded_abbrev: bool = False,
) -> Dict[str, Set[str]]:
    """
    Discover verbatim phrase occurrences from Pydantic models.

    Args:
        model_list: List of Pydantic models to scan
        source_patterns: Patterns to search for (from instrument list)
        field_paths: Field paths to search in
        output_path: Optional path to write verbatim TSV
        fails_output_path: Optional path to write failed patterns TSV
        pattern_to_expected_tinyids: Optional dict mapping pattern → set of expected
            tinyIds for filtered discovery. When provided, each pattern is only
            searched in texts from its expected tinyIds.
        n_workers: Number of parallel workers (0=auto, 1=sequential)
        allow_abbrev_variants: If True, abbreviation parentheticals match variants
            e.g., (PHQ) will also match (PHQ-9), (PHQ-15), etc.
        allow_embedded_abbrev: If True, allow optional abbreviations between words
            e.g., "Scale Long" can match "Scale (GDS) Long"

    Returns:
        Dict mapping verbatim_phrase → set of tinyIds
    """
    # Extract text spans
    logger.info(f"Extracting text from {len(model_list)} models...")
    texts_with_ids = extract_texts_from_models(model_list, field_paths)

    # Compile flexible patterns
    logger.info(f"Compiling {len(source_patterns)} flexible patterns...")
    compiled = compile_flexible_patterns(
        source_patterns,
        allow_abbrev_variants=allow_abbrev_variants,
        allow_embedded_abbrev=allow_embedded_abbrev,
    )

    # Discover verbatim occurrences
    if pattern_to_expected_tinyids:
        logger.info("Discovering verbatim occurrences (tinyId-filtered mode)...")
    else:
        logger.info("Discovering verbatim occurrences (full scan mode)...")

    def progress(current, total):
        if pattern_to_expected_tinyids:
            logger.info(f"  Progress: {current}/{total} patterns processed")
        else:
            logger.info(f"  Progress: {current}/{total} texts scanned")

    verbatim_map, failed_patterns = discover_verbatim_occurrences(
        texts_with_ids,
        compiled,
        progress_callback=progress,
        pattern_to_expected_tinyids=pattern_to_expected_tinyids,
        n_workers=n_workers
    )

    # Write output if requested
    if output_path:
        write_verbatim_tsv(verbatim_map, output_path, sort_by_length=True)

    # Write failed patterns if requested
    if fails_output_path and failed_patterns:
        write_failed_patterns_tsv(failed_patterns, fails_output_path)

    return verbatim_map


def verbatim_to_phrase_map(
    verbatim_data: List[Tuple[str, Set[str]]],
    field_paths: List[str],
    replace_with: str = ""
) -> List[Tuple[str, str, str, Optional[Set[str]]]]:
    """
    Convert verbatim discovery results to phrase_map format.

    Args:
        verbatim_data: List of (verbatim, tinyIds) from discovery or TSV
        field_paths: Field paths to apply to
        replace_with: Replacement string (default: empty)

    Returns:
        List of (path, phrase, replace, tinyIds) tuples
    """
    phrase_map = []

    for verbatim, tinyids in verbatim_data:
        for path in field_paths:
            # tinyIds is the set of IDs that actually contain this phrase
            phrase_map.append((path, verbatim, replace_with, tinyids if tinyids else None))

    logger.info(
        f"Created phrase map: {len(verbatim_data)} verbatim phrases × "
        f"{len(field_paths)} paths = {len(phrase_map)} entries"
    )
    return phrase_map


def discover_and_strip_workflow(
    model_list: List[BaseModel],
    source_patterns: List[str],
    field_paths: List[str],
    verbatim_output: Optional[str] = None,
    verbatim_input: Optional[str] = None,
    n_workers: int = 1
) -> List[BaseModel]:
    """
    Complete discover-then-strip workflow.

    If verbatim_input is provided, skip discovery and use pre-discovered patterns.
    Otherwise, discover verbatim occurrences first.

    Args:
        model_list: List of Pydantic models to process
        source_patterns: Patterns to search for (used if no verbatim_input)
        field_paths: Field paths for discovery and stripping
        verbatim_output: Optional path to write discovered verbatim TSV
        verbatim_input: Optional path to pre-discovered verbatim TSV
        n_workers: Number of parallel workers for stripping

    Returns:
        List of models with phrases stripped
    """
    from logic.phrase_stripper import strip_phrases

    # Phase 1: Get verbatim patterns
    if verbatim_input and Path(verbatim_input).exists():
        # Load pre-discovered patterns
        logger.info(f"Loading pre-discovered verbatim patterns from {verbatim_input}")
        verbatim_data = load_verbatim_tsv(verbatim_input)
    else:
        # Discover verbatim patterns
        logger.info("Phase 1: Discovering verbatim occurrences...")
        verbatim_map = discover_verbatim_from_models(
            model_list,
            source_patterns,
            field_paths,
            output_path=verbatim_output
        )
        # Convert dict to list format
        verbatim_data = [(v, ids) for v, ids in verbatim_map.items()]
        # Sort by length descending for longest-first processing
        verbatim_data.sort(key=lambda x: len(x[0]), reverse=True)

    if not verbatim_data:
        logger.warning("No verbatim patterns discovered - nothing to strip")
        return model_list

    # Phase 2: Strip using exact verbatim patterns
    logger.info(f"Phase 2: Stripping {len(verbatim_data)} verbatim patterns...")
    phrase_map = verbatim_to_phrase_map(verbatim_data, field_paths)

    cleaned = strip_phrases(model_list, phrase_map, n_workers=n_workers)

    return cleaned
