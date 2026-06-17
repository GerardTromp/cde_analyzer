"""
Core phrase mining logic using iterative descending k-mer detection.

This module implements the main phrase mining algorithm:
1. Extract and tokenize text from CDE fields
2. Iteratively mine k-mers from k_max down to k_min
3. Mask detected phrases to prevent re-detection
4. Filter by frequency and tinyId support

Advanced features (Aho-Corasick, de Bruijn, subsumption, anchor extension)
are implemented in separate utility modules.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from CDE_Schema.CDE_Item import CDEItem
from utils.phrase_miner_vocab import Vocabulary

logger = logging.getLogger(__name__)

# Punctuation characters that may trail a phrase and should be included in verbatim text
# These are printable non-alphanumeric characters commonly found at phrase boundaries
TRAILING_PUNCTUATION = frozenset([
    ')', ']', '}',           # Closing brackets
    '.', ',', ';', ':',      # Sentence/clause punctuation
    '?', '!',                # Question/exclamation marks
    "'", '"', '"', '"',      # Quotes (straight and curly)
    '-', '–', '—',           # Hyphens and dashes
    '/', '\\',               # Slashes
    '%', '°',                # Percent, degree
])

# Characters that may precede a phrase (for potential future left extension)
LEADING_PUNCTUATION = frozenset([
    '(', '[', '{',           # Opening brackets
    "'", '"', '"', '"',      # Quotes
    '-', '–', '—',           # Hyphens and dashes
])


@dataclass
class CDERef:
    """Reference to source CDE document and field path"""
    tinyId: str
    field_path: str           # e.g., "designations[0].designation"
    token_span: Tuple[int, int]  # (start_tok, end_tok) in token sequence
    verbatim_text: Optional[str] = None  # Original text for this occurrence
    char_span: Optional[Tuple[int, int]] = None  # Character offsets in source


@dataclass
class TokenSeq:
    """Token sequence with masking state and verbatim tracking"""
    tokens: List[int]                    # Vocab token IDs (lemmatized)
    cde_ref: CDERef
    mask_owner: List[Optional[str]]      # phrase_id that owns each token (None = unmasked)
    original_tokens: Optional[List[str]] = None  # Original tokens before lemmatization
    original_text: Optional[str] = None          # Full original text of this field
    char_offsets: Optional[List[Tuple[int, int]]] = None  # (start, end) char positions per token


@dataclass
class Phrase:
    """Detected phrase with metadata"""
    phrase_id: str            # Unique identifier (sequential: phrase_00001, phrase_00002, ...)
    token_ids: Tuple[int, ...]  # Token sequence (vocab IDs)
    text: str                 # Human-readable text
    frequency: int            # Total occurrence count
    distinct_tinyids: Set[str]  # Unique documents containing phrase
    k: int                    # Original k-mer length (before extension)
    occurrences: List[CDERef] # All occurrence locations
    extension_method: str     # "kmer", "debruijn", or "anchor"


@dataclass
class KmerCount:
    """K-mer with frequency and occurrence information"""
    kmer: Tuple[int, ...]
    frequency: int
    tinyids: Set[str]
    occurrences: List[CDERef]


@dataclass
class DedupResult:
    """Result of whole-text dedup for a single unique text."""
    text: str                    # Normalized field text (whitespace-collapsed)
    tinyids: Set[str]            # CDEs sharing this exact text
    field_path_sample: str       # Example field path (for logging)


@dataclass
class MinerConfig:
    """Configuration for phrase mining pipeline"""
    k_max: int = 25
    k_min: int = 3
    freq_min: int = 3         # Minimum frequency per k-bin
    min_distinct_tinyids: int = 2
    field_names: List[str] = field(default_factory=lambda: ["designation", "definition"])
    remove_stopwords: bool = True
    lemmatize: bool = True
    skip_debruijn: bool = True  # Set to False to enable de Bruijn extension
    skip_anchor: bool = True    # Defer to future enhancement
    use_aho_corasick: bool = True  # Use Aho-Corasick for masking (faster)
    generate_histograms: bool = False
    histogram_output_dir: Optional[Path] = None  # Directory for histogram output
    # Instrument extraction (pre-processing)
    extract_instruments: bool = False  # Extract "as part of <Instrument>" patterns
    min_instrument_words: int = 3      # Minimum words in instrument name
    extract_abbreviation_only: bool = False  # Second pass: extract "as part of (ACRONYM)" patterns
    extract_supplementary: bool = False  # Third pass: extract non-Title-Case instruments
    # Pre-loaded instrument patterns for masking (from curated list)
    instrument_patterns: Optional[Set[str]] = None  # Patterns to pre-mask before k-mer mining
    # Context-aware masking (Option D): uses instrument names with context detection
    context_aware_masking: bool = False  # If True, use context-aware masking instead of exact patterns
    # Whole-text dedup pre-pass
    dedup_enabled: bool = True           # Hash field texts, emit shared ones as phrases
    dedup_min_count: int = 2             # Min CDEs sharing identical text
    dedup_min_tokens: int = 3            # Min tokens to emit (skip trivial matches)
    # Text extension (post-loop recovery of truncated high-frequency phrases)
    prefix_consolidation: bool = True    # Enable text extension of high-frequency phrases
    prefix_min_tinyids: int = 20         # Min tinyId coverage to attempt extension
    extension_min_pct: float = 0.5       # Min fraction of occurrences sharing a right extension
    extension_max_words: int = 5         # Max words of right context to check
    # Ledger-informed pre-masking
    ledger_patterns: Optional[Set[str]] = None  # "remove" patterns from curation ledger


def dedup_field_texts(items: List[CDEItem], config: MinerConfig) -> List[DedupResult]:
    """
    Stage 0a: Identify field texts shared by multiple CDEs.

    O(n) pass: hash each field text (whitespace-normalized), group by hash,
    return texts with count >= dedup_min_count.

    Args:
        items: List of CDEItem objects
        config: Mining configuration (uses field_names, dedup_min_count)

    Returns:
        List of DedupResult objects for texts shared by enough CDEs.
    """
    import hashlib

    # hash -> { text, tinyids set, field_path }
    text_groups: dict = defaultdict(lambda: {"text": None, "tinyids": set(), "field_path": ""})

    for item in items:
        if not item.tinyId:
            continue
        text_spans = extract_field_texts(item, config.field_names)
        for field_path, text in text_spans:
            normalized = " ".join(text.split())
            if not normalized:
                continue
            h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
            group = text_groups[h]
            if group["text"] is None:
                group["text"] = normalized
                group["field_path"] = field_path
            group["tinyids"].add(item.tinyId)

    results = []
    for group in text_groups.values():
        if len(group["tinyids"]) >= config.dedup_min_count:
            results.append(DedupResult(
                text=group["text"],
                tinyids=group["tinyids"],
                field_path_sample=group["field_path"],
            ))

    # Sort by tinyId count descending (most shared first)
    results.sort(key=lambda r: len(r.tinyids), reverse=True)
    return results


def mine_phrases(items: List[CDEItem], config: MinerConfig):
    """
    Main phrase mining pipeline.

    Args:
        items: List of CDEItem objects to process
        config: Mining configuration

    Returns:
        Tuple of (phrases, token_seqs, vocab, verbatim_tracker, instrument_catalog, dedup_phrases):
        - phrases: List of detected k-mer phrases (excludes dedup phrases)
        - token_seqs: Token sequences for each text span (with masking state)
        - vocab: Vocabulary mapping
        - verbatim_tracker: VerbatimTracker for lemma→variants lookup
        - instrument_catalog: InstrumentCatalog if extract_instruments=True, else None
        - dedup_phrases: List of whole-text dedup Phrase objects (for separate curation)
    """
    # Stage 0a: Whole-text dedup pre-pass (before tokenization)
    dedup_results = []
    if config.dedup_enabled:
        dedup_results = dedup_field_texts(items, config)
        if dedup_results:
            logger.info(
                f"Dedup pre-pass: {len(dedup_results)} texts shared by "
                f"{config.dedup_min_count}+ CDEs (top: {len(dedup_results[0].tinyids)} tinyIds)"
            )

    # Stage 1: Extract and tokenize text spans from CDE fields
    # (optionally with instrument extraction and pre-masking)
    token_seqs, vocab, verbatim_tracker, instrument_catalog = extract_token_sequences(items, config)
    logger.info(f"Extracted {len(token_seqs)} token sequences, vocab size {len(vocab)}")
    if instrument_catalog:
        n_instruments = len(instrument_catalog.instruments)
        n_matches = sum(len(m) for m in instrument_catalog.instruments.values())
        logger.info(f"Extracted {n_instruments} distinct instruments ({n_matches} total matches)")

    all_phrases = []
    phrase_id_counter = 0

    # Stage 0b: Convert dedup results to Phrases (only those exceeding k_max)
    # Short duplicates (tokens <= k_max) are found naturally by k-mer mining.
    # Long duplicates (tokens > k_max) can't be reached by k-mer mining and need
    # dedup identification. No masking — sub-phrases within dedup'd texts remain
    # visible to k-mer mining so their counts aren't artificially reduced.
    if config.dedup_enabled and dedup_results:
        # Build index: normalized_text -> [TokenSeq indices]
        text_to_seqs: dict = defaultdict(list)
        for idx, seq in enumerate(token_seqs):
            if seq.original_text:
                norm = " ".join(seq.original_text.split())
                text_to_seqs[norm].append(idx)

        dedup_phrases = []
        n_short_skipped = 0
        for dedup in dedup_results:
            matching_seq_idxs = text_to_seqs.get(dedup.text, [])
            if not matching_seq_idxs:
                continue

            # Use the first matching sequence's tokens as the phrase token_ids
            first_seq = token_seqs[matching_seq_idxs[0]]
            token_ids = tuple(first_seq.tokens)

            if len(token_ids) < config.dedup_min_tokens:
                continue

            # Only emit phrases that exceed k_max — shorter ones are found by k-mer mining
            if len(token_ids) <= config.k_max:
                n_short_skipped += 1
                continue

            # Build text from vocab
            text = " ".join(vocab.get_tokens(list(token_ids)))

            # Build occurrences (no masking — let k-mer mining see sub-phrases)
            phrase_id_str = f"dedup_{phrase_id_counter:05d}"
            occurrences = []
            matched_tinyids = set()
            for seq_idx in matching_seq_idxs:
                seq = token_seqs[seq_idx]
                matched_tinyids.add(seq.cde_ref.tinyId)
                occ = CDERef(
                    tinyId=seq.cde_ref.tinyId,
                    field_path=seq.cde_ref.field_path,
                    token_span=(0, len(seq.tokens)),
                    verbatim_text=seq.original_text,
                    char_span=(0, len(seq.original_text)) if seq.original_text else None,
                )
                occurrences.append(occ)

            phrase = Phrase(
                phrase_id=phrase_id_str,
                token_ids=token_ids,
                text=text,
                frequency=len(occurrences),
                distinct_tinyids=matched_tinyids,
                k=len(token_ids),
                occurrences=occurrences,
                extension_method="dedup",
            )
            dedup_phrases.append(phrase)
            phrase_id_counter += 1

        # Do NOT add dedup phrases to all_phrases — they go to separate curation output
        logger.info(
            f"Dedup: {len(dedup_phrases)} phrases exceeding k_max={config.k_max}, "
            f"{n_short_skipped} short duplicates left to k-mer mining"
        )

    # Initialize histogram collector if enabled
    histogram_collector = None
    if config.generate_histograms and config.histogram_output_dir:
        from utils.histogram_generator import HistogramCollector
        histogram_collector = HistogramCollector(config.histogram_output_dir)
        logger.info("Histogram generation enabled")

    # Stage 2: Iterative descending k-mer mining
    for k in range(config.k_max, config.k_min - 1, -1):
        logger.info(f"Processing k={k}")

        # Count k-mers in unmasked regions
        kmer_counts = count_kmers_with_masking(token_seqs, k, config.freq_min)
        logger.info(f"  Found {len(kmer_counts)} frequent k-mers")

        if not kmer_counts:
            continue

        # Collect histogram data (tinyid counts before min_tinyids filter)
        if histogram_collector:
            tinyid_counts = [len(kc.tinyids) for kc in kmer_counts]
            histogram_collector.add_kmer_counts(k, tinyid_counts)

        # Stage 3: De Bruijn graph extension
        if not config.skip_debruijn:
            from utils.debruijn_graph import debruijn_extend_bin
            original_count = len(kmer_counts)
            kmer_counts = debruijn_extend_bin(kmer_counts, vocab, config)
            if len(kmer_counts) != original_count:
                logger.info(f"  De Bruijn: {original_count} -> {len(kmer_counts)} k-mers")

        # Stage 4: Convert k-mers to phrases
        new_phrases = []
        for kmer_count in kmer_counts:
            # Determine extension method based on k-mer length vs original k
            extension_method = "debruijn" if len(kmer_count.kmer) > k else "kmer"
            phrase = kmer_count_to_phrase(kmer_count, phrase_id_counter, k, vocab, extension_method)
            phrase_id_counter += 1

            # Stage 5: Filter by tinyId support
            if len(phrase.distinct_tinyids) >= config.min_distinct_tinyids:
                new_phrases.append(phrase)

        all_phrases.extend(new_phrases)
        logger.info(f"  Added {len(new_phrases)} phrases (filtered by min_tinyids={config.min_distinct_tinyids})")

        # Stage 6: Mask detected phrases
        if config.use_aho_corasick:
            mask_phrases_aho_corasick(token_seqs, new_phrases)
        else:
            mask_phrases_naive(token_seqs, new_phrases)

    # Stage 7: Text extension — recover truncated high-frequency phrases
    if config.prefix_consolidation:
        extended_phrases, phrase_id_counter = extend_frequent_phrases(
            all_phrases, token_seqs, vocab, config, phrase_id_counter
        )
        if extended_phrases:
            all_phrases.extend(extended_phrases)
            logger.info(
                f"Text extension: {len(extended_phrases)} extended phrases emitted"
            )

    # Stage 8: Generate histograms if enabled
    if histogram_collector:
        histogram_collector.generate_histograms(
            min_tinyids_threshold=config.min_distinct_tinyids
        )

    logger.info(f"Total phrases detected: {len(all_phrases)}")
    # Collect dedup phrases (may be empty list if dedup disabled or no matches)
    _dedup_phrases = dedup_phrases if (config.dedup_enabled and dedup_results) else []
    return all_phrases, token_seqs, vocab, verbatim_tracker, instrument_catalog, _dedup_phrases


def extract_instruments_only(items: List[CDEItem], config: MinerConfig):
    """
    Phase 1 mode: extract instrument patterns only, without k-mer mining.

    This is a lightweight alternative to mine_phrases() for the two-phase workflow:
    1. Phase 1: Extract instruments with lower min_tinyids threshold for discovery
    2. User curates instruments_verbatim.tsv (remove false positives)
    3. Phase 2: Run full phrase mining with curated instrument list for pre-masking

    Optionally performs a second pass to extract abbreviation-only references
    like "as part of (PHQ-9)" using known acronyms from the first pass.

    Args:
        items: List of CDEItem objects to process
        config: Mining configuration (uses extract_instruments, min_instrument_words,
                extract_abbreviation_only)

    Returns:
        InstrumentCatalog with detected instrument patterns (or None if disabled)
    """
    from utils.instrument_extractor import InstrumentExtractor, InstrumentCatalog
    from utils.phrase_extraction import tokenize_text_with_positions

    extractor = InstrumentExtractor(min_name_words=config.min_instrument_words)
    catalog = InstrumentCatalog()

    # Store text spans for potential second pass
    text_spans_by_item = []

    for item in items:
        if not item.tinyId:
            continue

        # Extract text spans from specified fields
        text_spans = extract_field_texts(item, config.field_names)
        text_spans_by_item.append((item, text_spans))

        for field_path, text in text_spans:
            # Tokenize to get character offsets (needed for token span computation)
            tokens_with_pos = tokenize_text_with_positions(text)
            if not tokens_with_pos:
                continue

            char_offsets = [t[1] for t in tokens_with_pos]

            # Extract instrument patterns
            matches = extractor.extract_from_text(text, item.tinyId, field_path)
            # Compute token spans
            matches = extractor.compute_token_spans(matches, char_offsets)

            for match in matches:
                catalog.add(match)

    n_instruments = len(catalog.instruments)
    n_matches = sum(len(m) for m in catalog.instruments.values())
    logger.info(f"Extracted {n_instruments} distinct instruments ({n_matches} total matches)")

    # Second pass: extract abbreviation-only patterns
    if config.extract_abbreviation_only:
        # Build acronym -> canonical name mapping from first pass
        acronym_map = catalog.get_acronym_to_name_map()
        logger.info(f"Built acronym map with {len(acronym_map)} known acronyms for second pass")

        abbrev_count = 0
        for item, text_spans in text_spans_by_item:
            if not item.tinyId:
                continue

            for field_path, text in text_spans:
                # Tokenize to get character offsets
                tokens_with_pos = tokenize_text_with_positions(text)
                if not tokens_with_pos:
                    continue

                char_offsets = [t[1] for t in tokens_with_pos]

                # Extract abbreviation-only patterns
                matches = extractor.extract_abbreviation_only(
                    text,
                    known_acronyms=acronym_map,
                    tinyId=item.tinyId,
                    field_path=field_path
                )
                # Compute token spans
                matches = extractor.compute_token_spans(matches, char_offsets)

                for match in matches:
                    catalog.add(match)
                    abbrev_count += 1

        if abbrev_count > 0:
            logger.info(f"Second pass: extracted {abbrev_count} abbreviation-only instrument references")

    # Third pass: extract supplementary patterns (non-Title-Case instruments)
    if config.extract_supplementary:
        logger.debug("Starting third pass: supplementary pattern extraction")
        supp_count = 0
        for item, text_spans in text_spans_by_item:
            if not item.tinyId:
                continue

            for field_path, text in text_spans:
                # Tokenize to get character offsets
                tokens_with_pos = tokenize_text_with_positions(text)
                if not tokens_with_pos:
                    continue

                char_offsets = [t[1] for t in tokens_with_pos]

                # Extract supplementary patterns
                matches = extractor.extract_supplementary_patterns(
                    text,
                    tinyId=item.tinyId,
                    field_path=field_path
                )
                # Compute token spans
                matches = extractor.compute_token_spans(matches, char_offsets)

                for match in matches:
                    catalog.add(match)
                    supp_count += 1

        if supp_count > 0:
            logger.info(f"Third pass: extracted {supp_count} supplementary pattern references")

    return catalog


def extract_token_sequences(items: List[CDEItem], config: MinerConfig):
    """
    Extract text from specified fields, tokenize, lemmatize, build vocabulary.

    Now also tracks original tokens for verbatim text recovery.
    Optionally extracts instrument patterns and pre-masks them.

    Args:
        items: List of CDEItem objects
        config: Mining configuration

    Returns:
        Tuple of (token_seqs, vocab, verbatim_tracker, instrument_catalog):
        - token_seqs: List of TokenSeq objects with original token tracking
        - vocab: Vocabulary object
        - verbatim_tracker: VerbatimTracker for lemma→variants lookup
        - instrument_catalog: InstrumentCatalog if extract_instruments=True, else None
    """
    from utils.phrase_extraction import tokenize_text_with_positions, make_lemma, STOPWORDS
    from utils.verbatim_tracker import VerbatimTracker

    # Conditional import for instrument extraction
    instrument_catalog = None
    instrument_extractor = None
    if config.extract_instruments:
        from utils.instrument_extractor import InstrumentExtractor, InstrumentCatalog
        instrument_extractor = InstrumentExtractor(min_name_words=config.min_instrument_words)
        instrument_catalog = InstrumentCatalog()

    vocab = Vocabulary()
    verbatim_tracker = VerbatimTracker(prefix_len=2)
    token_seqs = []

    for item in items:
        if not item.tinyId:
            continue

        # Extract text spans from specified fields
        text_spans = extract_field_texts(item, config.field_names)

        for field_path, text in text_spans:
            # Tokenize with position tracking for verbatim recovery
            tokens_with_pos = tokenize_text_with_positions(text)
            if not tokens_with_pos:
                continue

            # Separate tokens and positions
            original_tokens = [t[0] for t in tokens_with_pos]
            char_offsets = [t[1] for t in tokens_with_pos]

            # Extract instrument patterns BEFORE lemmatization (need original case)
            instrument_matches = []
            if instrument_extractor:
                instrument_matches = instrument_extractor.extract_from_text(
                    text, item.tinyId, field_path
                )
                # Compute token spans for masking
                instrument_matches = instrument_extractor.compute_token_spans(
                    instrument_matches, char_offsets
                )
                for match in instrument_matches:
                    instrument_catalog.add(match)

            # For lemmatization, we need lowercase tokens
            tokens_lower = [t.lower() for t in original_tokens]

            # Lemmatize if configured
            # Track index mapping for instrument token span translation
            old_to_new_index = None  # Maps original token index to post-stopword index

            if config.lemmatize:
                lemmas = make_lemma(tokens_lower, config.remove_stopwords, STOPWORDS)

                # Build lemma→original mapping for verbatim recovery
                # Note: After stopword removal, lists may have different lengths
                # We need to track which tokens were kept
                if config.remove_stopwords:
                    # Re-align: filter original_tokens and char_offsets to match lemmas
                    stopwords_lower = {s.lower() for s in STOPWORDS}
                    kept_indices = [i for i, t in enumerate(tokens_lower) if t not in stopwords_lower]

                    # Build mapping from old indices to new indices for token span translation
                    old_to_new_index = {}
                    for new_idx, old_idx in enumerate(kept_indices):
                        old_to_new_index[old_idx] = new_idx

                    original_tokens = [original_tokens[i] for i in kept_indices]
                    char_offsets = [char_offsets[i] for i in kept_indices]

                # Now register lemma→original mappings
                for orig, lemma in zip(original_tokens, lemmas):
                    verbatim_tracker.register_token(lemma, orig)

                tokens_str = lemmas
            else:
                tokens_str = tokens_lower

            if not tokens_str:  # Skip if no tokens remain after processing
                continue

            # Convert to vocab IDs
            token_ids = [vocab.add_token(t) for t in tokens_str]

            # Create TokenSeq with verbatim tracking
            cde_ref = CDERef(
                tinyId=item.tinyId,
                field_path=field_path,
                token_span=(0, len(token_ids))
            )

            # Initialize mask_owner (all unmasked)
            mask_owner = [None] * len(token_ids)

            # Pre-mask instrument tokens if extraction is enabled
            # This prevents them from being detected as separate phrases during k-mer mining
            if instrument_matches:
                for match in instrument_matches:
                    if match.token_span:
                        old_start, old_end = match.token_span
                        instrument_key = f"__INSTRUMENT__:{match.instrument_name}"

                        # Translate token span if stopwords were removed
                        if old_to_new_index is not None:
                            # Map old indices to new indices (skip indices that were removed)
                            new_start = None
                            new_end = None
                            for old_idx in range(old_start, old_end):
                                if old_idx in old_to_new_index:
                                    new_idx = old_to_new_index[old_idx]
                                    if new_start is None:
                                        new_start = new_idx
                                    new_end = new_idx + 1

                            if new_start is not None and new_end is not None:
                                for i in range(new_start, min(new_end, len(mask_owner))):
                                    mask_owner[i] = instrument_key
                        else:
                            # No stopword removal - use original indices
                            for i in range(old_start, min(old_end, len(mask_owner))):
                                mask_owner[i] = instrument_key

            # Pre-mask curated instrument patterns from --instrument-list
            # Two modes: exact pattern matching (default) or context-aware (Option D)
            if config.instrument_patterns:
                if config.context_aware_masking:
                    # Option D: Context-aware masking
                    # Uses instrument names extracted from patterns + context phrase detection
                    from utils.context_aware_masking import (
                        extract_instrument_names_from_patterns,
                        compute_context_aware_mask_ranges
                    )

                    # Extract instrument names from patterns (cached after first call)
                    if not hasattr(config, '_instrument_names_cache'):
                        config._instrument_names_cache = extract_instrument_names_from_patterns(
                            config.instrument_patterns
                        )
                        logger.info(f"Context-aware masking: {len(config._instrument_names_cache)} instrument names extracted")

                    # Compute mask ranges using context-aware matching
                    mask_ranges = compute_context_aware_mask_ranges(
                        text,
                        char_offsets,
                        config._instrument_names_cache,
                        old_to_new_index
                    )

                    # Apply masks
                    for token_start, token_end, mask_key in mask_ranges:
                        for i in range(token_start, min(token_end, len(mask_owner))):
                            if mask_owner[i] is None:  # Don't overwrite existing masks
                                mask_owner[i] = mask_key
                else:
                    # Original exact pattern matching (Option A or no expansion)
                    text_lower = text.lower()
                    for pattern in config.instrument_patterns:
                        pattern_lower = pattern.lower()
                        # Find all occurrences of the pattern in the text
                        start_pos = 0
                        while True:
                            idx = text_lower.find(pattern_lower, start_pos)
                            if idx == -1:
                                break
                            pattern_end = idx + len(pattern)
                            # Find token range that overlaps with this character range
                            # char_offsets contains (start, end) for each token
                            token_start = None
                            token_end = None
                            for ti, (cs, ce) in enumerate(char_offsets):
                                # Token overlaps if it starts before pattern ends AND ends after pattern starts
                                if cs < pattern_end and ce > idx:
                                    if token_start is None:
                                        token_start = ti
                                    token_end = ti + 1
                            # Mask the token range
                            if token_start is not None and token_end is not None:
                                mask_key = f"__CURATED_INSTRUMENT__:{pattern[:50]}"
                                for i in range(token_start, min(token_end, len(mask_owner))):
                                    if mask_owner[i] is None:  # Don't overwrite existing masks
                                        mask_owner[i] = mask_key
                            start_pos = idx + 1  # Continue searching for more occurrences

            # Pre-mask ledger "remove" patterns (same approach as instrument pre-masking)
            if config.ledger_patterns:
                text_lower = text.lower()
                for pattern in config.ledger_patterns:
                    pattern_lower = pattern.lower()
                    start_pos = 0
                    while True:
                        idx = text_lower.find(pattern_lower, start_pos)
                        if idx == -1:
                            break
                        pattern_end = idx + len(pattern)
                        token_start = None
                        token_end = None
                        for ti, (cs, ce) in enumerate(char_offsets):
                            if cs < pattern_end and ce > idx:
                                if token_start is None:
                                    token_start = ti
                                token_end = ti + 1
                        if token_start is not None and token_end is not None:
                            mask_key = f"__LEDGER_REMOVE__:{pattern[:50]}"
                            for i in range(token_start, min(token_end, len(mask_owner))):
                                if mask_owner[i] is None:
                                    mask_owner[i] = mask_key
                        start_pos = idx + 1

            token_seqs.append(TokenSeq(
                tokens=token_ids,
                cde_ref=cde_ref,
                mask_owner=mask_owner,
                original_tokens=original_tokens,
                original_text=text,
                char_offsets=char_offsets
            ))

    return token_seqs, vocab, verbatim_tracker, instrument_catalog


def extract_field_texts(item: CDEItem, field_names: List[str]) -> List[Tuple[str, str]]:
    """
    Extract text values from specified fields in CDEItem.

    Args:
        item: CDEItem object
        field_names: List of field names to extract

    Returns:
        List of (field_path, text) tuples
    """
    results = []

    # Designations (names, questions)
    if "designation" in field_names and item.designations:
        for i, desig in enumerate(item.designations):
            if desig.designation:
                path = f"designations[{i}].designation"
                results.append((path, desig.designation))

    # Definitions (descriptions)
    if "definition" in field_names and item.definitions:
        for i, defn in enumerate(item.definitions):
            if defn.definition:
                path = f"definitions[{i}].definition"
                results.append((path, defn.definition))

    # Permissible values (if specified)
    if "valueMeaningName" in field_names:
        if item.valueDomain and item.valueDomain.permissibleValues:
            for i, pv in enumerate(item.valueDomain.permissibleValues):
                if pv.valueMeaningName:
                    path = f"valueDomain.permissibleValues[{i}].valueMeaningName"
                    results.append((path, pv.valueMeaningName))

    if "valueMeaningDefinition" in field_names:
        if item.valueDomain and item.valueDomain.permissibleValues:
            for i, pv in enumerate(item.valueDomain.permissibleValues):
                if pv.valueMeaningDefinition:
                    path = f"valueDomain.permissibleValues[{i}].valueMeaningDefinition"
                    results.append((path, pv.valueMeaningDefinition))

    return results


def extend_verbatim_span(text: str, char_start: int, char_end: int) -> Tuple[int, int]:
    """
    Extend verbatim character span to include adjacent punctuation.

    When lemmatization removes trailing punctuation from tokens (e.g., "outcome)" becomes
    "outcome"), the verbatim span should still include that punctuation to capture the
    complete original phrase.

    Args:
        text: The full original text
        char_start: Starting character position
        char_end: Ending character position (exclusive)

    Returns:
        Tuple of (extended_start, extended_end) character positions
    """
    text_len = len(text)

    # Extend right to include trailing punctuation
    while char_end < text_len and text[char_end] in TRAILING_PUNCTUATION:
        char_end += 1

    # Extend left to include leading punctuation (optional, for completeness)
    while char_start > 0 and text[char_start - 1] in LEADING_PUNCTUATION:
        char_start -= 1

    return char_start, char_end


def count_kmers_with_masking(token_seqs: List[TokenSeq], k: int, freq_min: int) -> List[KmerCount]:
    """
    Count k-mers in unmasked regions only, capturing verbatim text per occurrence.

    Args:
        token_seqs: List of TokenSeq objects
        k: K-mer length
        freq_min: Minimum frequency threshold

    Returns:
        List of KmerCount objects (filtered by freq_min)
    """
    kmer_map = defaultdict(lambda: {"freq": 0, "tinyids": set(), "occurrences": []})

    for seq in token_seqs:
        # Find unmasked k-mer windows
        for i in range(len(seq.tokens) - k + 1):
            # Check if this k-mer window is unmasked
            if all(owner is None for owner in seq.mask_owner[i:i+k]):
                kmer_tuple = tuple(seq.tokens[i:i+k])
                kmer_map[kmer_tuple]["freq"] += 1
                kmer_map[kmer_tuple]["tinyids"].add(seq.cde_ref.tinyId)

                # Extract verbatim text for this occurrence
                verbatim_text = None
                char_span = None
                if seq.char_offsets and seq.original_text:
                    try:
                        char_start = seq.char_offsets[i][0]
                        char_end = seq.char_offsets[i + k - 1][1]
                        # Extend span to include adjacent punctuation
                        char_start, char_end = extend_verbatim_span(
                            seq.original_text, char_start, char_end
                        )
                        verbatim_text = seq.original_text[char_start:char_end]
                        char_span = (char_start, char_end)
                    except (IndexError, TypeError):
                        pass  # Fall back to None if offsets unavailable

                # Record occurrence location with verbatim text
                occ = CDERef(
                    tinyId=seq.cde_ref.tinyId,
                    field_path=seq.cde_ref.field_path,
                    token_span=(i, i+k),
                    verbatim_text=verbatim_text,
                    char_span=char_span
                )
                kmer_map[kmer_tuple]["occurrences"].append(occ)

    # Filter by frequency and convert to list
    results = []
    for kmer, data in kmer_map.items():
        if data["freq"] >= freq_min:
            results.append(KmerCount(
                kmer=kmer,
                frequency=data["freq"],
                tinyids=data["tinyids"],
                occurrences=data["occurrences"]
            ))

    return results


def mask_phrases_naive(token_seqs: List[TokenSeq], phrases: List[Phrase]):
    """
    Mark tokens as masked using naive pattern matching.

    This is a simple O(n*m*k) implementation where:
    - n = total tokens across all sequences
    - m = number of phrases
    - k = average phrase length

    For large datasets, use mask_phrases_aho_corasick() instead.

    Args:
        token_seqs: List of TokenSeq objects (modified in-place)
        phrases: List of Phrase objects to mask
    """
    for seq in token_seqs:
        for phrase in phrases:
            # Simple sliding window match
            phrase_len = len(phrase.token_ids)
            for i in range(len(seq.tokens) - phrase_len + 1):
                # Check if this window matches phrase and is unmasked
                if all(seq.mask_owner[i+j] is None for j in range(phrase_len)):
                    if tuple(seq.tokens[i:i+phrase_len]) == phrase.token_ids:
                        # Mask this occurrence (first-come-first-served)
                        for j in range(phrase_len):
                            seq.mask_owner[i+j] = phrase.phrase_id


def mask_phrases_aho_corasick(token_seqs: List[TokenSeq], phrases: List[Phrase]):
    """
    Mark tokens as masked using Aho-Corasick multi-pattern matching.

    This is an O(n + m + z) implementation where:
    - n = total tokens across all sequences
    - m = total pattern length (sum of all phrase lengths)
    - z = number of matches found

    Significantly faster than naive matching for large phrase sets.

    Args:
        token_seqs: List of TokenSeq objects (modified in-place)
        phrases: List of Phrase objects to mask
    """
    from utils.aho_corasick_token import build_automaton

    if not phrases:
        return

    # Build Aho-Corasick automaton from phrase token sequences
    patterns = {p.phrase_id: list(p.token_ids) for p in phrases}
    automaton = build_automaton(patterns)

    # Match patterns in each token sequence
    for seq in token_seqs:
        matches = automaton.search(seq.tokens)

        # Sort matches by start position, then by length (longer first)
        # This ensures longer phrases get priority at same position
        matches.sort(key=lambda m: (m[1], -(m[2] - m[1])))

        # Mark matched regions as owned (first-come-first-served)
        for phrase_id, start_idx, end_idx in matches:
            # Check if this region is still unmasked
            if all(seq.mask_owner[i] is None for i in range(start_idx, end_idx)):
                for i in range(start_idx, end_idx):
                    seq.mask_owner[i] = phrase_id


def kmer_count_to_phrase(kmer_count: KmerCount, phrase_id: int, k: int, vocab: Vocabulary,
                         extension_method: str = "kmer") -> Phrase:
    """
    Convert KmerCount to Phrase object.

    Args:
        kmer_count: KmerCount object
        phrase_id: Sequential phrase ID number
        k: K-mer length (original k value from mining loop)
        vocab: Vocabulary for text conversion
        extension_method: How this phrase was detected ("kmer", "debruijn", or "anchor")

    Returns:
        Phrase object
    """
    text = " ".join(vocab.get_tokens(list(kmer_count.kmer)))
    return Phrase(
        phrase_id=f"phrase_{phrase_id:05d}",
        token_ids=kmer_count.kmer,
        text=text,
        frequency=kmer_count.frequency,
        distinct_tinyids=kmer_count.tinyids,
        k=k,
        occurrences=kmer_count.occurrences,
        extension_method=extension_method
    )


# ---------------------------------------------------------------------------
# Stage 7: Text extension — recover truncated high-frequency phrases
# ---------------------------------------------------------------------------

def _extract_right_context(
    original_text: str,
    char_end: int,
    max_words: int,
) -> List[str]:
    """
    Extract up to *max_words* whitespace-delimited words from *original_text*
    starting at character position *char_end*.

    Returns a list of progressive extensions: ["+1 word", "+2 words", ...].
    Each entry is the cumulative extension text (e.g. ["related", "related to",
    "related to anesthetic"]).
    """
    remainder = original_text[char_end:].lstrip()
    if not remainder:
        return []
    words = remainder.split(None, max_words)[:max_words]
    extensions: List[str] = []
    for i in range(len(words)):
        extensions.append(" ".join(words[:i + 1]))
    return extensions


def _build_text_index(
    token_seqs: List['TokenSeq'],
) -> Dict[Tuple[str, str], str]:
    """
    Build a mapping ``(tinyId, field_path) → original_text`` from token
    sequences for fast lookup during extension analysis.
    """
    index: Dict[Tuple[str, str], str] = {}
    for seq in token_seqs:
        if seq.original_text:
            key = (seq.cde_ref.tinyId, seq.cde_ref.field_path)
            index[key] = seq.original_text
    return index


def extend_frequent_phrases(
    all_phrases: List['Phrase'],
    token_seqs: List['TokenSeq'],
    vocab: 'Vocabulary',
    config: 'MinerConfig',
    phrase_id_counter: int,
) -> Tuple[List['Phrase'], int]:
    """
    Stage 7: Text extension — recover truncated high-frequency phrases.

    For each phrase whose tinyId coverage meets *prefix_min_tinyids*, examine
    the right context (verbatim text) at every occurrence.  If a common
    extension appears in >= *extension_min_pct* of occurrences, emit the
    extended phrase.  Then cascade: re-analyze the residual occurrences for
    their own common extension, repeating until coverage drops below the
    tinyId threshold.

    Works on **verbatim text** — avoids lemmatization inconsistencies that
    caused the token-ID prefix trie to fail on hyphenated words.

    Returns
    -------
    (new_extended_phrases, updated_phrase_id_counter)
    """
    if not all_phrases:
        return [], phrase_id_counter

    text_index = _build_text_index(token_seqs)

    # Existing phrase texts (case-insensitive) for dedup — only phrases with
    # sufficient tinyId coverage.  Low-coverage fragmented phrases must NOT
    # block the extension from being emitted with correct aggregated coverage.
    existing_texts: Set[str] = set()
    for p in all_phrases:
        if len(p.distinct_tinyids) >= config.prefix_min_tinyids:
            existing_texts.add(p.text.lower())
            for occ in p.occurrences:
                if occ.verbatim_text:
                    existing_texts.add(occ.verbatim_text.strip().lower())

    # Sort by distinct tinyId count descending — process highest-coverage first
    candidates = sorted(
        all_phrases,
        key=lambda p: len(p.distinct_tinyids),
        reverse=True,
    )

    # Ledger pattern set (Level A filtering — skip known "remove" patterns)
    ledger_lower: Optional[Set[str]] = None
    if config.ledger_patterns:
        ledger_lower = {p.lower() for p in config.ledger_patterns}

    new_phrases: List[Phrase] = []
    max_words = config.extension_max_words
    min_pct = config.extension_min_pct

    for phrase in candidates:
        if len(phrase.distinct_tinyids) < config.prefix_min_tinyids:
            continue  # below tinyId threshold; skip

        # Gather occurrences with usable char_span
        usable_occs: List[CDERef] = []
        for occ in phrase.occurrences:
            if occ.char_span is not None:
                key = (occ.tinyId, occ.field_path)
                if key in text_index:
                    usable_occs.append(occ)

        if len(usable_occs) < config.prefix_min_tinyids:
            continue

        # Cascade loop: extend, then re-analyze residual
        remaining_occs = usable_occs
        while len({occ.tinyId for occ in remaining_occs}) >= config.prefix_min_tinyids:
            # Build progressive right-context extensions for each occurrence
            occ_extensions: List[Tuple[CDERef, List[str]]] = []
            for occ in remaining_occs:
                orig_text = text_index[(occ.tinyId, occ.field_path)]
                exts = _extract_right_context(orig_text, occ.char_span[1], max_words)
                occ_extensions.append((occ, exts))

            # Count frequency of each progressive extension
            # extension_counts[ext_text] = list of occurrences that have it
            best_ext_text: Optional[str] = None
            best_ext_occs: List[CDERef] = []

            # Try from longest to shortest — pick the longest above threshold
            for width in range(max_words, 0, -1):
                ext_map: Dict[str, List[CDERef]] = {}
                for occ, exts in occ_extensions:
                    if len(exts) >= width:
                        ext_text = exts[width - 1].lower()
                        ext_map.setdefault(ext_text, []).append(occ)

                # Find most frequent extension at this width
                for ext_text, occs in ext_map.items():
                    if len(occs) >= min_pct * len(remaining_occs):
                        if best_ext_text is None or len(occs) > len(best_ext_occs):
                            best_ext_text = ext_text
                            best_ext_occs = occs
                # If found at this width, use it (longest above threshold)
                if best_ext_text is not None:
                    break

            if best_ext_text is None:
                break  # no extension above threshold; stop cascade

            # Build extended text using verbatim phrase text + extension
            # Use the first occurrence's verbatim text as the base
            base_text = phrase.occurrences[0].verbatim_text or phrase.text
            extended_text = base_text.rstrip() + " " + best_ext_text

            # Dedup: skip if this text already exists
            if extended_text.lower() in existing_texts:
                # Remove matched occurrences and continue cascade on residual
                matched_set = set(id(o) for o in best_ext_occs)
                remaining_occs = [o for o in remaining_occs if id(o) not in matched_set]
                continue

            # Level A: skip if ledger says "remove"
            if ledger_lower and extended_text.lower() in ledger_lower:
                matched_set = set(id(o) for o in best_ext_occs)
                remaining_occs = [o for o in remaining_occs if id(o) not in matched_set]
                continue

            # Build extended occurrences with updated char_span
            extended_occs: List[CDERef] = []
            extended_tinyids: Set[str] = set()
            n_ext_words = len(best_ext_text.split())
            for occ in best_ext_occs:
                orig_text = text_index[(occ.tinyId, occ.field_path)]
                # Walk n_ext_words forward from char_span end
                pos = occ.char_span[1]
                words_found = 0
                while words_found < n_ext_words and pos < len(orig_text):
                    # Skip whitespace
                    while pos < len(orig_text) and orig_text[pos].isspace():
                        pos += 1
                    if pos >= len(orig_text):
                        break
                    # Skip word characters
                    while pos < len(orig_text) and not orig_text[pos].isspace():
                        pos += 1
                    words_found += 1

                char_end_new = pos
                verbatim_new = orig_text[occ.char_span[0]:char_end_new]
                extended_occs.append(CDERef(
                    tinyId=occ.tinyId,
                    field_path=occ.field_path,
                    token_span=occ.token_span,  # approximate; token span not updated
                    verbatim_text=verbatim_new,
                    char_span=(occ.char_span[0], char_end_new),
                ))
                extended_tinyids.add(occ.tinyId)

            if len(extended_tinyids) < config.prefix_min_tinyids:
                break

            # Tokenize extended text for token_ids field (for downstream compatibility)
            token_ids = tuple(
                vocab.tok2id.get(w, vocab.add_token(w))
                for w in extended_text.lower().split()
            )

            ext_phrase = Phrase(
                phrase_id=f"phrase_{phrase_id_counter:05d}",
                token_ids=token_ids,
                text=extended_text,
                frequency=len(extended_occs),
                distinct_tinyids=extended_tinyids,
                k=len(token_ids),
                occurrences=extended_occs,
                extension_method="text_extension",
            )
            new_phrases.append(ext_phrase)
            existing_texts.add(extended_text.lower())
            phrase_id_counter += 1
            logger.info(
                f"  Extended '{base_text}' → '{extended_text}' "
                f"(tinyids={len(extended_tinyids)}, "
                f"occurrences={len(extended_occs)})"
            )

            # Cascade: remove matched occurrences, continue with residual
            matched_set = set(id(o) for o in best_ext_occs)
            remaining_occs = [o for o in remaining_occs if id(o) not in matched_set]

    return new_phrases, phrase_id_counter
