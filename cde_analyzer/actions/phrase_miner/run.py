"""Orchestration layer for phrase_miner action"""

import json
import logging
from argparse import Namespace
from pathlib import Path
from typing import List, Optional, Set

from CDE_Schema.CDE_Item import CDEItem
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


def load_instrument_list(
    spec: str,
    expand_variants: bool = False,
    include_name_only: bool = True
) -> Set[str]:
    """
    Load instrument patterns from a TSV file for pre-masking.

    Args:
        spec: File specification in format 'filename' or 'filename,column_name'.
              If column_name is omitted, defaults to 'full_match'.
        expand_variants: If True, generate spelling/punctuation variants for better matching.
                        Handles spacing around parentheses, trailing punctuation, prefix variations.
        include_name_only: When expanding variants, also include bare instrument names
                          without 'as part of' prefix for broader matching.

    Returns:
        Set of pattern strings to mask during tokenization.

    Raises:
        FileNotFoundError: If the specified file doesn't exist.
        ValueError: If the specified column is not found in the file.
    """
    # Parse spec: "filename" or "filename,column"
    if ',' in spec:
        parts = spec.split(',', 1)
        filepath = parts[0].strip()
        column_name = parts[1].strip()
    else:
        filepath = spec.strip()
        column_name = 'full_match'  # Default column

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Instrument list file not found: {filepath}")

    patterns = set()
    with path.open('r', encoding='utf-8') as f:
        # Read header to find column index
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        try:
            col_idx = headers.index(column_name)
        except ValueError:
            raise ValueError(
                f"Column '{column_name}' not found in {filepath}. "
                f"Available columns: {', '.join(headers)}"
            )

        # Read data rows
        for line_num, line in enumerate(f, start=2):
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')
            if col_idx < len(fields):
                pattern = fields[col_idx].strip()
                if pattern:
                    patterns.add(pattern)

    logger.info(f"Loaded {len(patterns)} base instrument patterns from {filepath} (column: {column_name})")

    # Optionally expand variants (Option A)
    if expand_variants:
        from utils.pattern_variant_generator import expand_pattern_set
        patterns = expand_pattern_set(
            patterns,
            include_name_only=include_name_only,
            collect_acronyms=True
        )
        logger.info(f"Expanded to {len(patterns)} patterns with variants")

    return patterns


@graceful_interrupt
def run_action(args: Namespace):
    """
    Main entry point for phrase_miner action.
    Loads data, executes mining pipeline, writes output.

    Two-phase workflow supported:
    - Phase 1 (--instruments-only): Extract instruments only for curation
    - Phase 2 (normal): Full phrase mining, optionally with curated instrument list

    Args:
        args: Parsed command-line arguments
    """
    # Lazy import heavy modules
    from logic.phrase_miner import mine_phrases, extract_instruments_only, MinerConfig, Phrase
    from logic.phrase_anchor_extend import extend_anchors

    # 1. Load data
    logger.info(f"Loading data from {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    items = [CDEItem.model_validate(obj) for obj in raw]
    logger.info(f"Loaded {len(items)} CDE items")

    # 2. Build configuration
    # De Bruijn is disabled by default, enabled with --enable-debruijn
    # (--skip-debruijn kept for compatibility but --enable-debruijn takes precedence)
    skip_debruijn = not getattr(args, 'enable_debruijn', False)
    if hasattr(args, 'skip_debruijn') and args.skip_debruijn:
        skip_debruijn = True

    # Aho-Corasick is enabled by default
    use_aho_corasick = not getattr(args, 'no_aho_corasick', False)

    # Anchor extension: disabled by default, enabled with --enable-anchor
    skip_anchor = not getattr(args, 'enable_anchor', False)
    if hasattr(args, 'skip_anchor') and args.skip_anchor:
        skip_anchor = True

    # Subsumption filtering: disabled by default, enabled with --enable-subsumption
    enable_subsumption = getattr(args, 'enable_subsumption', False)

    # Instrument extraction: disabled by default, enabled with --extract-instruments
    extract_instruments = getattr(args, 'extract_instruments', False)
    min_instrument_words = getattr(args, 'min_instrument_words', 3)
    extract_abbreviation_only = getattr(args, 'extract_abbreviation_only', False)
    extract_supplementary = getattr(args, 'extract_supplementary', False)

    # Phase 1 mode: instruments only, skip phrase mining outputs
    instruments_only = getattr(args, 'instruments_only', False)
    if instruments_only:
        extract_instruments = True  # --instruments-only implies --extract-instruments

    # Load curated instrument list for pre-masking (Phase 2)
    instrument_patterns = None
    instrument_list_spec = getattr(args, 'instrument_list', None)
    expand_variants = getattr(args, 'expand_variants', False)
    include_name_only = getattr(args, 'include_name_only', True)

    if instrument_list_spec:
        try:
            instrument_patterns = load_instrument_list(
                instrument_list_spec,
                expand_variants=expand_variants,
                include_name_only=include_name_only
            )
        except FileNotFoundError as e:
            logger.error(f"Instrument list error: {e}")
            raise SystemExit(1)
        except ValueError as e:
            logger.error(f"Instrument list error: {e}")
            raise SystemExit(1)

    # Load additional instrument lists (e.g., curated 2-word instruments)
    additional_lists = getattr(args, 'additional_instrument_lists', None)
    if additional_lists:
        if instrument_patterns is None:
            instrument_patterns = set()
        for spec in additional_lists:
            try:
                additional_patterns = load_instrument_list(
                    spec,
                    expand_variants=expand_variants,
                    include_name_only=include_name_only
                )
                logger.info(f"Merging {len(additional_patterns)} patterns from {spec}")
                instrument_patterns.update(additional_patterns)
            except FileNotFoundError as e:
                logger.error(f"Additional instrument list error: {e}")
                raise SystemExit(1)
            except ValueError as e:
                logger.error(f"Additional instrument list error: {e}")
                raise SystemExit(1)

    # Histogram output directory (only set if histograms enabled)
    histogram_output_dir = Path(args.output_dir) if args.histograms else None

    # Context-aware masking (Option D)
    context_aware_masking = getattr(args, 'context_aware_masking', False)

    config = MinerConfig(
        k_max=args.k_max,
        k_min=args.k_min,
        freq_min=args.freq_min,
        min_distinct_tinyids=args.min_tinyids,
        field_names=args.fields,
        lemmatize=args.lemmatize,
        remove_stopwords=args.remove_stopwords,
        skip_debruijn=skip_debruijn,
        skip_anchor=skip_anchor,
        use_aho_corasick=use_aho_corasick,
        generate_histograms=args.histograms,
        histogram_output_dir=histogram_output_dir,
        extract_instruments=extract_instruments,
        min_instrument_words=min_instrument_words,
        extract_abbreviation_only=extract_abbreviation_only,
        extract_supplementary=extract_supplementary,
        instrument_patterns=instrument_patterns,
        context_aware_masking=context_aware_masking,
    )

    # Log configuration
    logger.info(f"Configuration: k={args.k_min}-{args.k_max}, freq_min={args.freq_min}, "
                f"min_tinyids={args.min_tinyids}")
    if instruments_only:
        logger.info("Phase 1 mode: extracting instruments only (phrase outputs disabled)")
    if instrument_patterns:
        masking_mode = "context-aware (Option D)" if context_aware_masking else "exact pattern (Option A)"
        logger.info(f"Pre-masking {len(instrument_patterns)} instrument patterns using {masking_mode}")
    logger.info(f"Features: debruijn={'enabled' if not skip_debruijn else 'disabled'}, "
                f"aho_corasick={'enabled' if use_aho_corasick else 'disabled'}, "
                f"subsumption={'enabled' if enable_subsumption else 'disabled'}, "
                f"anchor={'enabled' if not skip_anchor else 'disabled'}, "
                f"instrument_extract={'enabled' if extract_instruments else 'disabled'}, "
                f"abbrev_only={'enabled' if extract_abbreviation_only else 'disabled'}, "
                f"supplementary={'enabled' if extract_supplementary else 'disabled'}")

    # 3. Execute pipeline
    if instruments_only:
        # Phase 1: lightweight instrument extraction only
        logger.info("Starting instrument extraction (phase 1)...")
        instrument_catalog = extract_instruments_only(items, config)

        # Early exit to output writing for instruments
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if instrument_catalog and instrument_catalog.instruments:
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
                logger.info(f"Phase 1 complete with family detection. Output files:")
                for output_type, path in outputs.items():
                    logger.info(f"  - {output_type}: {path.name}")
                logger.info(f"Curate instruments needing review, then run phase 2 with --instrument-list.")
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
                logger.info(f"Phase 1 complete. Curate instruments_verbatim.tsv, then run phase 2 with --instrument-list.")
        else:
            logger.warning("No instruments extracted. Check input data contains 'as part of' patterns.")

        return 0  # Skip phrase mining

    # Phase 2 (normal): full phrase mining pipeline
    logger.info("Starting phrase mining pipeline...")
    phrases, token_seqs, vocab, verbatim_tracker, instrument_catalog = mine_phrases(items, config)
    logger.info(f"Mined {len(phrases)} phrases (vocabulary size: {len(vocab)})")

    # Log verbatim tracker statistics
    stats = verbatim_tracker.get_statistics()
    logger.info(f"Verbatim tracker: {stats['unique_lemmas']} lemmas, "
                f"{stats['total_variants']} variants, "
                f"avg {stats['avg_variants_per_lemma']:.1f} per lemma")

    # 4. Optional subsumption filtering
    if enable_subsumption:
        from utils.subsumption_filter import subsumption_filter
        original_count = len(phrases)
        phrases = subsumption_filter(phrases, require_tinyid_overlap=True)
        logger.info(f"Subsumption filter: {original_count} -> {len(phrases)} phrases")

    # 5. Optional anchor extension
    extended_phrases = []
    if not skip_anchor:
        logger.info("Performing anchor extension...")
        extended_phrases = extend_anchors(phrases, token_seqs, vocab, config)
        if extended_phrases:
            logger.info(f"Extended {len(extended_phrases)} phrases")

    # 6. Write outputs (Phase 2 / normal mode - instruments-only returns early above)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Get verbatim filtering options
    verbatim_case_sensitive = getattr(args, 'verbatim_case_sensitive', False)

    write_phrases_tsv(phrases, output_dir / "phrases.tsv", vocab)
    write_occurrences_tsv(phrases, output_dir / "occurrences.tsv")
    write_verbatim_phrases_tsv(phrases, output_dir / "verbatim_phrases.tsv",
                               case_sensitive=verbatim_case_sensitive)
    write_verbatim_variants_tsv(verbatim_tracker, output_dir / "verbatim_variants.tsv")

    # Write verbatim templates (extracts structural patterns from multi-form phrases)
    templates_count = write_verbatim_templates_tsv(
        phrases, output_dir / "verbatim_templates.tsv",
        case_sensitive=verbatim_case_sensitive
    )
    if templates_count > 0:
        logger.info(f"Extracted {templates_count} verbatim templates (phrases with 2+ variants)")

    if extended_phrases:
        write_extended_tsv(extended_phrases, output_dir / "extended.tsv", vocab)

    # Write instruments.tsv and instruments_verbatim.tsv if instrument extraction was enabled
    if instrument_catalog:
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
        else:
            # Original behavior without family detection
            instruments_count = write_instruments_tsv(
                instrument_catalog, output_dir / "instruments.tsv",
                min_tinyids=args.min_tinyids
            )
            logger.info(f"Wrote {instruments_count} instruments to instruments.tsv (summary)")

            # Write verbatim variants for curation (one row per exact instrument name form)
            verbatim_count = write_instruments_verbatim_tsv(
                instrument_catalog, output_dir / "instruments_verbatim.tsv",
                min_tinyids=args.min_tinyids
            )
            logger.info(f"Wrote {verbatim_count} instrument variants to instruments_verbatim.tsv (for curation)")

    # Log verbatim phrase statistics
    verbatim_count = sum(1 for p in phrases for occ in p.occurrences if occ.verbatim_text)
    logger.info(f"Results written to {output_dir}")
    logger.info(f"Occurrences with verbatim text: {verbatim_count}")

    # Optional phrase family analysis (post-mining analysis of non-instrument phrases)
    analyze_phrase_families = getattr(args, 'analyze_phrase_families', False)
    if analyze_phrase_families:
        from logic.phrase_family_analyzer import (
            analyze_phrase_families as run_family_analysis,
            FamilyAnalysisConfig
        )

        logger.info("Analyzing phrase families using prefix/suffix patterns...")

        config = FamilyAnalysisConfig(
            min_prefix_words=getattr(args, 'min_prefix_words', 2),
            min_suffix_words=getattr(args, 'min_suffix_words', 1),
            min_family_size=getattr(args, 'min_family_size', 3),
            max_families=getattr(args, 'max_families', 100),
            include_prefixes=True,
            include_suffixes=True
        )

        verbatim_tsv = output_dir / "verbatim_phrases.tsv"
        if verbatim_tsv.exists():
            families = run_family_analysis(
                str(verbatim_tsv),
                str(output_dir),
                config
            )
            logger.info(f"Phrase family analysis: {len(families)} families discovered")
            logger.info(f"  - phrase_families.tsv: Family summaries")
            logger.info(f"  - phrase_family_members.tsv: Detailed membership")
        else:
            logger.warning(f"Cannot analyze phrase families: {verbatim_tsv} not found")

    return 0


def write_phrases_tsv(phrases: List, path: Path, vocab):
    """
    Write phrases.tsv: phrase_id, text, k, frequency, n_tinyids, extension_method

    Args:
        phrases: List of Phrase objects
        path: Output file path
        vocab: Vocabulary object (not used in current version)
    """
    with path.open('w', encoding='utf-8') as f:
        f.write("phrase_id\ttext\tk\tfrequency\tn_tinyids\textension_method\n")
        for p in phrases:
            f.write(f"{p.phrase_id}\t{p.text}\t{p.k}\t{p.frequency}\t"
                   f"{len(p.distinct_tinyids)}\t{p.extension_method}\n")


def write_verbatim_phrases_tsv(phrases: List, path: Path, case_sensitive: bool = False):
    """
    Write verbatim_phrases.tsv: maps lemmatized phrases to unique verbatim forms.

    For each lemmatized phrase, extracts all unique verbatim surface forms from
    occurrences. One lemmatized phrase may map to multiple verbatim phrases
    (e.g., "patient report outcome" → "Patient Reported Outcome", "patient-reported outcomes").

    Applies three-stage filtering to verbatim forms:
    1. Coalescing: Overlapping fragments from the same tinyId set are merged into
       a single longer string. This handles sliding window artifacts where
       "harmful and usually..." and "and usually subject..." become one merged string.
    2. Subsumption (conservative): Shorter verbatim strings that are substrings
       of longer ones WITH tinyId overlap are removed.
    3. Subsumption (refinement): Remaining stragglers that are exact substrings
       of longer forms are merged into the longer form, combining tinyIds and counts.
       This catches cases where different document sets produced the same substring.

    Columns: phrase_id, lemma_text, verbatim_text, verbatim_count, tinyids,
             prefix_diff, suffix_diff, diff_summary

    The diff columns annotate differences between multiple verbatim forms of the
    same phrase_id, helping humans understand why forms weren't merged:
    - prefix_diff: Content missing from prefix compared to longest form
    - suffix_diff: Content missing from suffix compared to longest form
    - diff_summary: Human-readable summary of divergent portions

    For phrases with only one verbatim form, diff columns are empty.

    Args:
        phrases: List of Phrase objects with occurrences containing verbatim_text
        path: Output file path
        case_sensitive: If True, use case-sensitive comparison for coalescing and
                        subsumption. This preserves case variants (e.g., "Patient
                        Reported" vs "patient reported") for QC purposes. Default
                        False uses case-insensitive matching which produces cleaner output.
    """
    from collections import defaultdict
    from utils.verbatim_coalesce import coalesce_verbatim_groups
    from utils.verbatim_diff import annotate_verbatim_differences

    with path.open('w', encoding='utf-8') as f:
        f.write("phrase_id\tlemma_text\tverbatim_text\tverbatim_count\ttinyids\tprefix_diff\tsuffix_diff\tdiff_summary\n")

        for p in phrases:
            # Group occurrences by verbatim text
            verbatim_groups = defaultdict(lambda: {"count": 0, "tinyids": set()})

            for occ in p.occurrences:
                verbatim = occ.verbatim_text if occ.verbatim_text else ""
                # Normalize whitespace for grouping
                verbatim_normalized = " ".join(verbatim.split())
                if verbatim_normalized:
                    verbatim_groups[verbatim_normalized]["count"] += 1
                    verbatim_groups[verbatim_normalized]["tinyids"].add(occ.tinyId)

            # Stage 1: Coalesce overlapping fragments with same tinyId set
            # Convert defaultdict to regular dict for coalescing
            verbatim_dict = {k: dict(v) for k, v in verbatim_groups.items()}
            coalesced_groups = coalesce_verbatim_groups(
                verbatim_dict,
                case_sensitive=case_sensitive,
                min_overlap=10
            )

            # Stage 2: Conservative subsumption (requires tinyId overlap)
            verbatim_list = list(coalesced_groups.keys())
            subsumed_stage2 = set()

            # Sort by length descending so longer strings are processed first
            verbatim_list.sort(key=len, reverse=True)

            for i, long_verbatim in enumerate(verbatim_list):
                if long_verbatim in subsumed_stage2:
                    continue

                # Prepare comparison strings based on case sensitivity setting
                if case_sensitive:
                    long_compare = long_verbatim
                else:
                    long_compare = long_verbatim.lower()

                for j in range(i + 1, len(verbatim_list)):
                    short_verbatim = verbatim_list[j]
                    if short_verbatim in subsumed_stage2:
                        continue

                    # Prepare comparison strings based on case sensitivity setting
                    if case_sensitive:
                        short_compare = short_verbatim
                    else:
                        short_compare = short_verbatim.lower()

                    # Check if shorter is a substring of longer
                    if short_compare in long_compare:
                        # Require tinyId overlap for conservative subsumption
                        long_tinyids = coalesced_groups[long_verbatim]["tinyids"]
                        short_tinyids = coalesced_groups[short_verbatim]["tinyids"]
                        if long_tinyids & short_tinyids:  # Non-empty intersection
                            subsumed_stage2.add(short_verbatim)

            # Stage 3: Refinement subsumption - merge exact substrings regardless of tinyId
            # This catches stragglers from different document sets that are true substrings
            remaining = [v for v in verbatim_list if v not in subsumed_stage2]
            remaining.sort(key=len, reverse=True)  # Re-sort after filtering

            # Build refined groups - merge shorter into longer if exact substring
            refined_groups = {}
            merged_into = {}  # Track which short forms merged into which long form

            for verbatim in remaining:
                if case_sensitive:
                    compare_key = verbatim
                else:
                    compare_key = verbatim.lower()

                # Check if this verbatim is a substring of any already-added longer form
                merged = False
                for existing_verbatim in list(refined_groups.keys()):
                    if case_sensitive:
                        existing_compare = existing_verbatim
                    else:
                        existing_compare = existing_verbatim.lower()

                    if compare_key in existing_compare and compare_key != existing_compare:
                        # Merge: add counts and tinyIds to the longer form
                        refined_groups[existing_verbatim]["count"] += coalesced_groups[verbatim]["count"]
                        refined_groups[existing_verbatim]["tinyids"].update(coalesced_groups[verbatim]["tinyids"])
                        merged_into[verbatim] = existing_verbatim
                        merged = True
                        break

                if not merged:
                    # Add as new entry (copy to avoid mutation issues)
                    refined_groups[verbatim] = {
                        "count": coalesced_groups[verbatim]["count"],
                        "tinyids": set(coalesced_groups[verbatim]["tinyids"])
                    }

            # Stage 3.5: Truncation subsumption - detect prefix/suffix truncations
            # This catches cases like "Short Form Health Survey" vs "Short Form Health"
            # where one form is a prefix or suffix of another (not a simple substring)
            MIN_SHARED_LEN = 20  # Minimum overlap to consider a truncation

            refined_list = list(refined_groups.keys())
            refined_list.sort(key=len, reverse=True)
            truncation_subsumed = set()

            for i, long_v in enumerate(refined_list):
                if long_v in truncation_subsumed:
                    continue

                long_cmp = long_v if case_sensitive else long_v.lower()

                for j in range(i + 1, len(refined_list)):
                    short_v = refined_list[j]
                    if short_v in truncation_subsumed:
                        continue

                    short_cmp = short_v if case_sensitive else short_v.lower()
                    short_len = len(short_cmp)

                    # Skip if already a substring (handled in Stage 3)
                    if short_cmp in long_cmp:
                        continue

                    # Check if short is a prefix truncation (short matches END of long)
                    if short_len >= MIN_SHARED_LEN and long_cmp.endswith(short_cmp):
                        refined_groups[long_v]["count"] += refined_groups[short_v]["count"]
                        refined_groups[long_v]["tinyids"].update(refined_groups[short_v]["tinyids"])
                        truncation_subsumed.add(short_v)
                        continue

                    # Check if short is a suffix truncation (short matches START of long)
                    if short_len >= MIN_SHARED_LEN and long_cmp.startswith(short_cmp):
                        refined_groups[long_v]["count"] += refined_groups[short_v]["count"]
                        refined_groups[long_v]["tinyids"].update(refined_groups[short_v]["tinyids"])
                        truncation_subsumed.add(short_v)
                        continue

            # Remove truncation-subsumed entries
            for subsumed in truncation_subsumed:
                del refined_groups[subsumed]

            # Stage 4: Annotate differences between multiple verbatim forms
            # This adds prefix_diff, suffix_diff, diff_summary columns
            annotate_verbatim_differences(refined_groups, case_sensitive)

            # Write one row per unique refined verbatim form
            for verbatim, data in sorted(refined_groups.items(), key=lambda x: -x[1]["count"]):
                # Escape for TSV
                verbatim_safe = verbatim.replace('\t', ' ').replace('\n', ' ').replace('\r', '')
                tinyids_str = "|".join(sorted(data["tinyids"]))
                prefix_diff = data.get("prefix_diff", "").replace('\t', ' ').replace('\n', ' ')
                suffix_diff = data.get("suffix_diff", "").replace('\t', ' ').replace('\n', ' ')
                diff_summary = data.get("diff_summary", "").replace('\t', ' ').replace('\n', ' ')
                f.write(f"{p.phrase_id}\t{p.text}\t{verbatim_safe}\t{data['count']}\t{tinyids_str}\t{prefix_diff}\t{suffix_diff}\t{diff_summary}\n")


def write_occurrences_tsv(phrases: List, path: Path):
    """
    Write occurrences.tsv with verbatim text column.

    Columns: phrase_id, tinyId, field_path, token_start, token_end, verbatim_text

    Args:
        phrases: List of Phrase objects
        path: Output file path
    """
    with path.open('w', encoding='utf-8') as f:
        f.write("phrase_id\ttinyId\tfield_path\ttoken_start\ttoken_end\tverbatim_text\n")
        for p in phrases:
            for occ in p.occurrences:
                # Handle verbatim text - escape tabs/newlines for TSV format
                verbatim = occ.verbatim_text if occ.verbatim_text else ""
                verbatim = verbatim.replace('\t', ' ').replace('\n', ' ').replace('\r', '')
                f.write(f"{p.phrase_id}\t{occ.tinyId}\t{occ.field_path}\t"
                       f"{occ.token_span[0]}\t{occ.token_span[1]}\t{verbatim}\n")


def write_verbatim_variants_tsv(tracker, path: Path):
    """
    Write verbatim_variants.tsv: lemma→variants dictionary for analysis.

    Columns: lemma, variants (pipe-separated), count

    Args:
        tracker: VerbatimTracker object
        path: Output file path
    """
    with path.open('w', encoding='utf-8') as f:
        f.write("lemma\tvariants\tcount\n")
        for lemma in sorted(tracker.lemma_to_variants.keys()):
            trie = tracker.lemma_to_variants[lemma]
            variants = trie.all_variants()
            if variants:
                # Sort variants for consistent output
                variants_str = "|".join(sorted(variants))
                f.write(f"{lemma}\t{variants_str}\t{len(variants)}\n")


def write_extended_tsv(extended: List, path: Path, vocab):
    """
    Write extended.tsv: original_phrase_id, extended_text, left_tokens, right_tokens, score

    Args:
        extended: List of AnchorExtension objects
        path: Output file path
        vocab: Vocabulary object
    """
    with path.open('w', encoding='utf-8') as f:
        f.write("original_phrase_id\textended_text\tleft_tokens\tright_tokens\tscore\n")
        for ext in extended:
            left_text = " ".join(vocab.get_tokens(ext.left_extension))
            right_text = " ".join(vocab.get_tokens(ext.right_extension))
            full_text = f"{left_text} {ext.original_phrase.text} {right_text}".strip()
            f.write(f"{ext.original_phrase.phrase_id}\t{full_text}\t"
                   f"{len(ext.left_extension)}\t{len(ext.right_extension)}\t{ext.score:.4f}\n")


def write_verbatim_templates_tsv(phrases: List, path: Path, case_sensitive: bool = False):
    """
    Write verbatim_templates.tsv: extracts structural templates from verbatim variants.

    For phrases with multiple verbatim forms, extracts the common core pattern and
    identifies variable slots (prefix, suffix, internal infixes) where forms diverge.
    Output is designed for programmatic use - slots contain regex patterns.

    Columns:
        phrase_id: Phrase identifier
        lemma_text: Lemmatized phrase text
        n_variants: Number of verbatim variants for this phrase
        core: The longest common substring shared by all variants
        template_regex: Full regex pattern matching all variants
        prefix_slot: Regex pattern for prefix variations (empty if none)
        prefix_variants: Pipe-separated list of observed prefix values
        suffix_slot: Regex pattern for suffix variations (empty if none)
        suffix_variants: Pipe-separated list of observed suffix values
        infix1_slot: Regex for first internal divergence (empty if none)
        infix1_variants: Pipe-separated list of first infix values
        infix2_slot: Regex for second internal divergence (empty if none)
        infix2_variants: Pipe-separated list of second infix values

    Only phrases with 2+ distinct verbatim forms are included (single-form phrases
    have no template to extract).

    Args:
        phrases: List of Phrase objects with occurrences containing verbatim_text
        path: Output file path
        case_sensitive: If True, use case-sensitive comparison for template extraction
    """
    from collections import defaultdict
    from utils.verbatim_coalesce import coalesce_verbatim_groups
    from utils.verbatim_template import extract_template, format_template_row

    templates_written = 0

    with path.open('w', encoding='utf-8') as f:
        # Write header
        f.write("phrase_id\tlemma_text\tn_variants\tcore\ttemplate_regex\t"
                "prefix_slot\tprefix_variants\tsuffix_slot\tsuffix_variants\t"
                "infix1_slot\tinfix1_variants\tinfix2_slot\tinfix2_variants\n")

        for p in phrases:
            # Group occurrences by verbatim text (same logic as verbatim_phrases)
            verbatim_groups = defaultdict(lambda: {"count": 0, "tinyids": set()})

            for occ in p.occurrences:
                verbatim = occ.verbatim_text if occ.verbatim_text else ""
                verbatim_normalized = " ".join(verbatim.split())
                if verbatim_normalized:
                    verbatim_groups[verbatim_normalized]["count"] += 1
                    verbatim_groups[verbatim_normalized]["tinyids"].add(occ.tinyId)

            # Apply same coalescing and subsumption as verbatim_phrases
            verbatim_dict = {k: dict(v) for k, v in verbatim_groups.items()}
            coalesced_groups = coalesce_verbatim_groups(
                verbatim_dict,
                case_sensitive=case_sensitive,
                min_overlap=10
            )

            # Apply subsumption stages (simplified - just get final forms)
            verbatim_list = list(coalesced_groups.keys())
            verbatim_list.sort(key=len, reverse=True)

            # Stage 2: Conservative subsumption
            subsumed = set()
            for i, long_v in enumerate(verbatim_list):
                if long_v in subsumed:
                    continue
                long_cmp = long_v if case_sensitive else long_v.lower()
                for j in range(i + 1, len(verbatim_list)):
                    short_v = verbatim_list[j]
                    if short_v in subsumed:
                        continue
                    short_cmp = short_v if case_sensitive else short_v.lower()
                    if short_cmp in long_cmp:
                        if coalesced_groups[long_v]["tinyids"] & coalesced_groups[short_v]["tinyids"]:
                            subsumed.add(short_v)

            # Stage 3: Refinement subsumption
            remaining = [v for v in verbatim_list if v not in subsumed]
            remaining.sort(key=len, reverse=True)

            refined_forms = []
            for verbatim in remaining:
                cmp_key = verbatim if case_sensitive else verbatim.lower()
                merged = False
                for existing in refined_forms:
                    existing_cmp = existing if case_sensitive else existing.lower()
                    if cmp_key in existing_cmp and cmp_key != existing_cmp:
                        merged = True
                        break
                if not merged:
                    refined_forms.append(verbatim)

            # Only extract template if multiple forms remain
            if len(refined_forms) < 2:
                continue

            # Extract template
            template = extract_template(refined_forms, p.phrase_id, case_sensitive)
            if not template:
                continue

            # Format and write row
            row = format_template_row(template)

            # Escape TSV special characters
            def escape_tsv(s):
                return s.replace('\t', ' ').replace('\n', ' ').replace('\r', '')

            f.write(f"{p.phrase_id}\t{p.text}\t{row['n_variants']}\t"
                   f"{escape_tsv(row['core'])}\t{escape_tsv(row['template_regex'])}\t"
                   f"{escape_tsv(row['prefix_slot'])}\t{escape_tsv(row['prefix_variants'])}\t"
                   f"{escape_tsv(row['suffix_slot'])}\t{escape_tsv(row['suffix_variants'])}\t"
                   f"{escape_tsv(row['infix1_slot'])}\t{escape_tsv(row['infix1_variants'])}\t"
                   f"{escape_tsv(row['infix2_slot'])}\t{escape_tsv(row['infix2_variants'])}\n")
            templates_written += 1

    return templates_written


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
