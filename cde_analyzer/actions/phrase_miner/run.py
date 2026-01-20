"""Orchestration layer for phrase_miner action"""

import json
import logging
from argparse import Namespace
from pathlib import Path
from typing import List

from CDE_Schema.CDE_Item import CDEItem

logger = logging.getLogger(__name__)


def run_action(args: Namespace):
    """
    Main entry point for phrase_miner action.
    Loads data, executes mining pipeline, writes output.

    Args:
        args: Parsed command-line arguments
    """
    # Lazy import heavy modules
    from logic.phrase_miner import mine_phrases, MinerConfig, Phrase
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
    )

    # Log configuration
    logger.info(f"Configuration: k={args.k_min}-{args.k_max}, freq_min={args.freq_min}, "
                f"min_tinyids={args.min_tinyids}")
    logger.info(f"Features: debruijn={'enabled' if not skip_debruijn else 'disabled'}, "
                f"aho_corasick={'enabled' if use_aho_corasick else 'disabled'}, "
                f"subsumption={'enabled' if enable_subsumption else 'disabled'}, "
                f"anchor={'enabled' if not skip_anchor else 'disabled'}")

    # 3. Execute mining pipeline (now returns verbatim_tracker)
    logger.info("Starting phrase mining pipeline...")
    phrases, token_seqs, vocab, verbatim_tracker = mine_phrases(items, config)
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

    # 6. Write outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get verbatim filtering options
    verbatim_case_sensitive = getattr(args, 'verbatim_case_sensitive', False)

    write_phrases_tsv(phrases, output_dir / "phrases.tsv", vocab)
    write_occurrences_tsv(phrases, output_dir / "occurrences.tsv")
    write_verbatim_phrases_tsv(phrases, output_dir / "verbatim_phrases.tsv",
                               case_sensitive=verbatim_case_sensitive)
    write_verbatim_variants_tsv(verbatim_tracker, output_dir / "verbatim_variants.tsv")
    if extended_phrases:
        write_extended_tsv(extended_phrases, output_dir / "extended.tsv", vocab)

    # Log verbatim phrase statistics
    verbatim_count = sum(1 for p in phrases for occ in p.occurrences if occ.verbatim_text)
    logger.info(f"Results written to {output_dir}")
    logger.info(f"Occurrences with verbatim text: {verbatim_count}")


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

    Applies subsumption filtering to verbatim forms: shorter verbatim strings that
    are substrings of longer verbatim strings (for the same phrase) are removed.
    This prevents output like "may lead to...", "lead to...", "to..." which are
    just different extraction windows of the same source text.

    Columns: phrase_id, lemma_text, verbatim_text, verbatim_count, tinyids

    Args:
        phrases: List of Phrase objects with occurrences containing verbatim_text
        path: Output file path
        case_sensitive: If True, use case-sensitive substring matching for subsumption.
                        This preserves case variants (e.g., "Patient Reported" vs
                        "patient reported") for QC purposes. Default False uses
                        case-insensitive matching which removes more duplicates.
    """
    from collections import defaultdict

    with path.open('w', encoding='utf-8') as f:
        f.write("phrase_id\tlemma_text\tverbatim_text\tverbatim_count\ttinyids\n")

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

            # Apply verbatim subsumption: remove shorter strings contained in longer ones
            verbatim_list = list(verbatim_groups.keys())
            subsumed = set()

            # Sort by length descending so longer strings are processed first
            verbatim_list.sort(key=len, reverse=True)

            for i, long_verbatim in enumerate(verbatim_list):
                if long_verbatim in subsumed:
                    continue

                # Prepare comparison strings based on case sensitivity setting
                if case_sensitive:
                    long_compare = long_verbatim
                else:
                    long_compare = long_verbatim.lower()

                for j in range(i + 1, len(verbatim_list)):
                    short_verbatim = verbatim_list[j]
                    if short_verbatim in subsumed:
                        continue

                    # Prepare comparison strings based on case sensitivity setting
                    if case_sensitive:
                        short_compare = short_verbatim
                    else:
                        short_compare = short_verbatim.lower()

                    # Check if shorter is a substring of longer
                    if short_compare in long_compare:
                        # Also require tinyId overlap for subsumption
                        long_tinyids = verbatim_groups[long_verbatim]["tinyids"]
                        short_tinyids = verbatim_groups[short_verbatim]["tinyids"]
                        if long_tinyids & short_tinyids:  # Non-empty intersection
                            subsumed.add(short_verbatim)

            # Write one row per unique non-subsumed verbatim form
            non_subsumed = [(v, verbatim_groups[v]) for v in verbatim_list if v not in subsumed]
            for verbatim, data in sorted(non_subsumed, key=lambda x: -x[1]["count"]):
                # Escape for TSV
                verbatim_safe = verbatim.replace('\t', ' ').replace('\n', ' ').replace('\r', '')
                tinyids_str = "|".join(sorted(data["tinyids"]))
                f.write(f"{p.phrase_id}\t{p.text}\t{verbatim_safe}\t{data['count']}\t{tinyids_str}\n")


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
