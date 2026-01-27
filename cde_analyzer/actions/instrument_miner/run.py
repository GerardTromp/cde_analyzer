"""Orchestration layer for instrument_miner action"""

import json
import logging
from argparse import Namespace
from pathlib import Path
from typing import Optional

from CDE_Schema.CDE_Item import CDEItem
from utils.file_utils import exit_if_missing, graceful_interrupt

logger = logging.getLogger(__name__)


@graceful_interrupt
def run_action(args: Namespace):
    """
    Main entry point for instrument_miner action.
    Extracts instrument patterns from CDE text fields.

    Args:
        args: Parsed command-line arguments
    """
    # Lazy import heavy modules
    from logic.phrase_miner import extract_instruments_only, MinerConfig

    # 1. Load data
    input_path = exit_if_missing(args.input, "Input file")
    logger.info(f"Loading data from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    items = [CDEItem.model_validate(obj) for obj in raw]
    logger.info(f"Loaded {len(items)} CDE items")

    # 2. Build configuration
    min_instrument_words = getattr(args, 'min_instrument_words', 3)
    extract_abbreviation_only = getattr(args, 'extract_abbreviation_only', False)
    extract_supplementary = getattr(args, 'extract_supplementary', False)

    config = MinerConfig(
        # K-mer params not used for instrument extraction, but required by MinerConfig
        k_max=25,
        k_min=3,
        freq_min=3,
        min_distinct_tinyids=args.min_tinyids,
        field_names=args.fields,
        lemmatize=True,
        remove_stopwords=False,
        skip_debruijn=True,
        skip_anchor=True,
        use_aho_corasick=True,
        generate_histograms=False,
        histogram_output_dir=None,
        extract_instruments=True,  # Always enabled for this action
        min_instrument_words=min_instrument_words,
        extract_abbreviation_only=extract_abbreviation_only,
        extract_supplementary=extract_supplementary,
        instrument_patterns=None,
        context_aware_masking=False,
    )

    # Log configuration
    logger.info(f"Configuration: min_tinyids={args.min_tinyids}, "
                f"min_instrument_words={min_instrument_words}")
    logger.info(f"Extraction modes: "
                f"abbrev_only={'enabled' if extract_abbreviation_only else 'disabled'}, "
                f"supplementary={'enabled' if extract_supplementary else 'disabled'}")

    # 3. Extract instruments
    logger.info("Starting instrument extraction...")
    instrument_catalog = extract_instruments_only(items, config)

    # 4. Write output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not instrument_catalog or not instrument_catalog.instruments:
        logger.warning("No instruments extracted. Check input data contains 'as part of' patterns.")
        return 0

    # Check if family detection is enabled
    detect_families = getattr(args, 'detect_families', False)
    family_summary = getattr(args, 'family_summary', False)
    family_threshold = getattr(args, 'family_confidence_threshold', 0.7)

    if detect_families:
        # Use enhanced family-aware output
        from logic.instrument_family_assigner import InstrumentFamilyAssigner

        logger.info(f"Assigning instrument families (threshold: {family_threshold})...")
        assigner = InstrumentFamilyAssigner(
            confidence_threshold=family_threshold,
            generate_family_summary=family_summary,
        )
        stats = assigner.assign_families(instrument_catalog)
        outputs = assigner.write_all_outputs(instrument_catalog, output_dir)

        logger.info(f"Family assignment: {stats.total_instruments} instruments, "
                    f"{stats.families_detected} families, "
                    f"{stats.needs_review_count} need review")
        logger.info(f"Instrument extraction complete with family detection. Output files:")
        for output_type, path in outputs.items():
            logger.info(f"  - {output_type}: {path.name}")
    else:
        # Original behavior without family detection
        instruments_count = write_instruments_tsv(
            instrument_catalog, output_dir / "instruments.tsv",
            min_tinyids=args.min_tinyids
        )
        logger.info(f"Wrote {instruments_count} instruments to instruments.tsv (summary)")

        verbatim_count = write_instruments_verbatim_tsv(
            instrument_catalog, output_dir / "instruments_verbatim.tsv",
            min_tinyids=args.min_tinyids
        )
        logger.info(f"Wrote {verbatim_count} instrument variants to instruments_verbatim.tsv (for curation)")

    logger.info("Next step: curate output, then run strip_discover with --pattern-list instruments_verbatim.tsv")
    return 0


def write_instruments_tsv(catalog, path: Path, min_tinyids: int = 2) -> int:
    """
    Write instruments.tsv with detected instrument patterns (summary view).

    Columns:
        instrument_id: Unique identifier (instrument_00001, etc.)
        normalized_name: Lowercase name for grouping
        canonical_name: Most common verbatim form
        acronym: Extracted acronym(s) (pipe-separated if multiple)
        frequency: Total occurrence count
        n_tinyids: Distinct document count
        tinyids: Pipe-separated document IDs
        example_contexts: First 3 full match examples

    Args:
        catalog: InstrumentCatalog with detected instruments
        path: Output file path
        min_tinyids: Minimum distinct tinyIds to include (filter)

    Returns:
        Number of instruments written
    """
    instruments_written = 0

    with path.open('w', encoding='utf-8') as f:
        f.write("instrument_id\tnormalized_name\tcanonical_name\tacronym\t"
                "frequency\tn_tinyids\ttinyids\texample_contexts\n")

        for norm_name, matches in sorted(catalog.instruments.items()):
            # Filter by minimum tinyId support
            tinyids = {m.tinyId for m in matches if m.tinyId}
            if len(tinyids) < min_tinyids:
                continue

            # Find most common verbatim form of instrument name
            name_counts = {}
            acronyms = set()
            for m in matches:
                name_counts[m.instrument_name] = name_counts.get(m.instrument_name, 0) + 1
                if m.acronym:
                    acronyms.add(m.acronym)

            canonical = max(name_counts.items(), key=lambda x: x[1])[0]
            acronym_str = "|".join(sorted(acronyms)) if acronyms else ""

            # Example contexts (first 3 full matches)
            examples = [m.full_match for m in matches[:3]]
            examples_str = " | ".join(examples).replace('\t', ' ').replace('\n', ' ')

            f.write(f"instrument_{instruments_written:05d}\t{norm_name}\t{canonical}\t"
                    f"{acronym_str}\t{len(matches)}\t{len(tinyids)}\t"
                    f"{'|'.join(sorted(tinyids))}\t{examples_str}\n")
            instruments_written += 1

    return instruments_written


def write_instruments_verbatim_tsv(catalog, path: Path, min_tinyids: int = 2) -> int:
    """
    Write instruments_verbatim.tsv with one row per verbatim instrument name.

    This EAV-style output is designed for human curation:
    - Group by normalized_name to see all variants of an instrument
    - verbatim_name: just the instrument name (for metadata)
    - full_match: complete "as part of..." phrase (for masking in pass 2)
    - Delete rows for false positives, keep good matches

    Columns:
        normalized_name: Lowercase name for grouping/sorting
        acronym: Acronym(s) associated with this normalized name
        verbatim_name: Exact instrument name only (for metadata)
        full_match: Complete matched phrase including "as part of" (for masking)
        frequency: How many times this exact form appears
        n_tinyids: Distinct document count for this form
        tinyids: Pipe-separated document IDs

    Args:
        catalog: InstrumentCatalog with detected instruments
        path: Output file path
        min_tinyids: Minimum distinct tinyIds for the normalized name (not per-variant)

    Returns:
        Number of verbatim variants written
    """
    variants_written = 0

    with path.open('w', encoding='utf-8') as f:
        f.write("normalized_name\tacronym\tverbatim_name\tfull_match\tfrequency\tn_tinyids\ttinyids\n")

        for norm_name, matches in sorted(catalog.instruments.items()):
            # Filter by minimum tinyId support at the normalized level
            all_tinyids = {m.tinyId for m in matches if m.tinyId}
            if len(all_tinyids) < min_tinyids:
                continue

            # Collect all acronyms for this normalized name
            acronyms = {m.acronym for m in matches if m.acronym}
            acronym_str = "|".join(sorted(acronyms)) if acronyms else ""

            # Group matches by verbatim instrument_name, collecting full_match variants
            verbatim_groups = {}
            for m in matches:
                vname = m.instrument_name
                if vname not in verbatim_groups:
                    verbatim_groups[vname] = {"count": 0, "tinyids": set(), "full_matches": set()}
                verbatim_groups[vname]["count"] += 1
                if m.tinyId:
                    verbatim_groups[vname]["tinyids"].add(m.tinyId)
                if m.full_match:
                    verbatim_groups[vname]["full_matches"].add(m.full_match)

            # Write one row per verbatim variant, sorted by frequency desc
            for vname, data in sorted(verbatim_groups.items(), key=lambda x: -x[1]["count"]):
                tinyids_str = "|".join(sorted(data["tinyids"]))
                # Escape TSV special characters
                vname_safe = vname.replace('\t', ' ').replace('\n', ' ').replace('\r', '')
                # Use longest full_match as representative (includes most context)
                full_matches = sorted(data["full_matches"], key=len, reverse=True)
                full_match_safe = full_matches[0].replace('\t', ' ').replace('\n', ' ').replace('\r', '') if full_matches else ""

                f.write(f"{norm_name}\t{acronym_str}\t{vname_safe}\t{full_match_safe}\t"
                        f"{data['count']}\t{len(data['tinyids'])}\t{tinyids_str}\n")
                variants_written += 1

    return variants_written
