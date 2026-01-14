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
    config = MinerConfig(
        k_max=args.k_max,
        k_min=args.k_min,
        freq_min=args.freq_min,
        min_distinct_tinyids=args.min_tinyids,
        field_names=args.fields,
        lemmatize=args.lemmatize,
        remove_stopwords=args.remove_stopwords,
        skip_debruijn=args.skip_debruijn,
        skip_anchor=args.skip_anchor,
        generate_histograms=args.histograms,
    )

    # 3. Execute mining pipeline
    logger.info("Starting phrase mining pipeline...")
    phrases, token_seqs, vocab = mine_phrases(items, config)
    logger.info(f"Mined {len(phrases)} phrases (vocabulary size: {len(vocab)})")

    # 4. Optional anchor extension (deferred to Phase 7+)
    extended_phrases = []
    if not args.skip_anchor:
        logger.info("Performing anchor extension...")
        extended_phrases = extend_anchors(phrases, token_seqs, vocab, config)
        if extended_phrases:
            logger.info(f"Extended {len(extended_phrases)} phrases")

    # 5. Write outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_phrases_tsv(phrases, output_dir / "phrases.tsv", vocab)
    write_occurrences_tsv(phrases, output_dir / "occurrences.tsv")
    if extended_phrases:
        write_extended_tsv(extended_phrases, output_dir / "extended.tsv", vocab)

    logger.info(f"Results written to {output_dir}")


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


def write_occurrences_tsv(phrases: List, path: Path):
    """
    Write occurrences.tsv: phrase_id, tinyId, field_path, token_start, token_end

    Args:
        phrases: List of Phrase objects
        path: Output file path
    """
    with path.open('w', encoding='utf-8') as f:
        f.write("phrase_id\ttinyId\tfield_path\ttoken_start\ttoken_end\n")
        for p in phrases:
            for occ in p.occurrences:
                f.write(f"{p.phrase_id}\t{occ.tinyId}\t{occ.field_path}\t"
                       f"{occ.token_span[0]}\t{occ.token_span[1]}\n")


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
