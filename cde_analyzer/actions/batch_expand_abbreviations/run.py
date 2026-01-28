"""Orchestration layer for batch_expand_abbreviations action"""

import csv
import json
import logging
from argparse import Namespace
from pathlib import Path
from typing import Dict, List, Set, Tuple

from CDE_Schema.CDE_Item import CDEItem
from utils.file_utils import exit_if_missing, graceful_interrupt

logger = logging.getLogger(__name__)


def load_abbreviations(tsv_path: str, column: str = "acronym") -> List[str]:
    """
    Load unique abbreviations from a TSV file.

    Args:
        tsv_path: Path to TSV file (typically instruments.tsv)
        column: Column name containing abbreviations

    Returns:
        List of unique abbreviations (sorted)
    """
    abbreviations: Set[str] = set()

    with open(tsv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')

        if column not in reader.fieldnames:
            available = ', '.join(reader.fieldnames)
            raise ValueError(f"Column '{column}' not found. Available: {available}")

        for row in reader:
            value = row.get(column, "").strip()
            if value:
                # Handle pipe-separated multiple abbreviations
                for abbrev in value.split("|"):
                    abbrev = abbrev.strip()
                    if abbrev and len(abbrev) >= 2:  # Skip single-char abbreviations
                        abbreviations.add(abbrev)

    return sorted(abbreviations)


def subset_by_text(
    data: List[Dict],
    text_filter: str,
    field_names: List[str],
) -> Tuple[List[Dict], Set[str]]:
    """
    Fast text-based subsetting without Pydantic validation.

    Returns raw dicts for speed - validation happens later if needed.
    """
    from logic.subset import record_matches_text

    results = []
    matched_tinyids: Set[str] = set()

    for record in data:
        if record_matches_text(record, text_filter, field_names, case_sensitive=False):
            results.append(record)
            tinyid = record.get("tinyId", "")
            if tinyid:
                matched_tinyids.add(tinyid)

    return results, matched_tinyids


def mine_phrases_from_subset(
    subset: List[Dict],
    k_max: int,
    k_min: int,
    min_tinyids: int,
    field_names: List[str],
) -> List[Dict]:
    """
    Run lightweight phrase mining on a subset.

    Returns list of phrase dicts with frequency info.
    """
    from logic.phrase_miner import MinerConfig, mine_phrases_from_items

    # Convert to CDEItem objects
    items = [CDEItem.model_validate(record) for record in subset]

    config = MinerConfig(
        k_max=k_max,
        k_min=k_min,
        freq_min=2,
        min_distinct_tinyids=min_tinyids,
        field_names=field_names,
        lemmatize=True,
        remove_stopwords=False,
        skip_debruijn=True,
        skip_anchor=True,
        use_aho_corasick=True,
        generate_histograms=False,
        histogram_output_dir=None,
        extract_instruments=False,
        min_instrument_words=3,
        extract_abbreviation_only=False,
        extract_supplementary=False,
        instrument_patterns=None,
        context_aware_masking=False,
    )

    # Run mining
    token_seqs, vocab, verbatim_tracker, _ = mine_phrases_from_items(items, config)

    # Extract phrases from verbatim tracker
    phrases = []
    if verbatim_tracker and verbatim_tracker.phrase_to_verbatim:
        for phrase_key, verbatim_info in verbatim_tracker.phrase_to_verbatim.items():
            # Get the most common verbatim form
            if verbatim_info.verbatim_forms:
                top_form = max(verbatim_info.verbatim_forms.items(), key=lambda x: x[1])
                phrases.append({
                    "phrase": top_form[0],
                    "frequency": verbatim_info.total_count,
                    "n_tinyids": len(verbatim_info.tinyids),
                    "tinyids": "|".join(sorted(verbatim_info.tinyids)[:10]),  # Limit for output
                })

    # Sort by frequency descending
    phrases.sort(key=lambda x: (-x["frequency"], -x["n_tinyids"]))

    return phrases


@graceful_interrupt
def run_action(args: Namespace):
    """
    Main entry point for batch_expand_abbreviations action.

    Iterates over abbreviations, subsets CDEs, and mines phrases
    to discover extended instrument names.
    """
    # 1. Load input data
    input_path = exit_if_missing(args.input, "Input file")
    abbrev_path = exit_if_missing(args.abbreviations, "Abbreviations file")

    logger.info(f"Loading CDE data from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} CDE records")

    # 2. Load abbreviations
    logger.info(f"Loading abbreviations from {abbrev_path}")
    abbreviations = load_abbreviations(abbrev_path, args.acronym_column)
    logger.info(f"Found {len(abbreviations)} unique abbreviations")

    # Apply skip filter
    skip_set = set(args.skip_abbreviations or [])
    if skip_set:
        abbreviations = [a for a in abbreviations if a not in skip_set]
        logger.info(f"After filtering: {len(abbreviations)} abbreviations")

    # 3. Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 4. Process each abbreviation
    all_expansions = []
    summary_rows = []

    for i, abbrev in enumerate(abbreviations):
        logger.info(f"[{i+1}/{len(abbreviations)}] Processing '{abbrev}'...")

        # Subset CDEs containing this abbreviation
        subset, matched_tinyids = subset_by_text(data, abbrev, args.fields)

        if len(subset) < args.min_subset_size:
            logger.info(f"  Skipping: only {len(subset)} CDEs (min: {args.min_subset_size})")
            summary_rows.append({
                "abbreviation": abbrev,
                "subset_size": len(subset),
                "status": "skipped_too_small",
                "top_phrase": "",
                "top_frequency": 0,
            })
            continue

        logger.info(f"  Found {len(subset)} CDEs containing '{abbrev}'")

        # Mine phrases from subset
        try:
            phrases = mine_phrases_from_subset(
                subset,
                k_max=args.k_max,
                k_min=args.k_min,
                min_tinyids=args.min_tinyids,
                field_names=args.fields,
            )
        except Exception as e:
            logger.warning(f"  Mining failed: {e}")
            summary_rows.append({
                "abbreviation": abbrev,
                "subset_size": len(subset),
                "status": "mining_failed",
                "top_phrase": "",
                "top_frequency": 0,
            })
            continue

        if not phrases:
            logger.info(f"  No phrases found")
            summary_rows.append({
                "abbreviation": abbrev,
                "subset_size": len(subset),
                "status": "no_phrases",
                "top_phrase": "",
                "top_frequency": 0,
            })
            continue

        # Take top N phrases
        top_phrases = phrases[:args.top_phrases]
        logger.info(f"  Found {len(phrases)} phrases, top: '{top_phrases[0]['phrase']}'")

        # Add to all expansions
        for phrase in top_phrases:
            all_expansions.append({
                "abbreviation": abbrev,
                "expanded_phrase": phrase["phrase"],
                "frequency": phrase["frequency"],
                "n_tinyids": phrase["n_tinyids"],
                "tinyids": phrase["tinyids"],
            })

        summary_rows.append({
            "abbreviation": abbrev,
            "subset_size": len(subset),
            "status": "success",
            "top_phrase": top_phrases[0]["phrase"],
            "top_frequency": top_phrases[0]["frequency"],
        })

    # 5. Write outputs
    # All expansions TSV
    expansions_path = output_dir / "expanded_phrases.tsv"
    with open(expansions_path, 'w', encoding='utf-8', newline='') as f:
        if all_expansions:
            writer = csv.DictWriter(f, fieldnames=all_expansions[0].keys(), delimiter='\t')
            writer.writeheader()
            writer.writerows(all_expansions)
    logger.info(f"Wrote {len(all_expansions)} expanded phrases to {expansions_path}")

    # Summary TSV
    summary_path = output_dir / "expansion_summary.tsv"
    with open(summary_path, 'w', encoding='utf-8', newline='') as f:
        if summary_rows:
            writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys(), delimiter='\t')
            writer.writeheader()
            writer.writerows(summary_rows)
    logger.info(f"Wrote summary to {summary_path}")

    # Print summary
    success_count = sum(1 for r in summary_rows if r["status"] == "success")
    print(f"\nBatch expansion complete:")
    print(f"  Abbreviations processed: {len(abbreviations)}")
    print(f"  Successful expansions: {success_count}")
    print(f"  Expanded phrases found: {len(all_expansions)}")
    print(f"  Output: {expansions_path}")

    return 0
