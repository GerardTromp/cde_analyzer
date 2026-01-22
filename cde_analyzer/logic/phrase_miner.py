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
from typing import List, Optional, Set, Tuple
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
    # Instrument extraction (pre-processing)
    extract_instruments: bool = False  # Extract "as part of <Instrument>" patterns
    min_instrument_words: int = 3      # Minimum words in instrument name
    # Pre-loaded instrument patterns for masking (from curated list)
    instrument_patterns: Optional[Set[str]] = None  # Patterns to pre-mask before k-mer mining


def mine_phrases(items: List[CDEItem], config: MinerConfig):
    """
    Main phrase mining pipeline.

    Args:
        items: List of CDEItem objects to process
        config: Mining configuration

    Returns:
        Tuple of (phrases, token_seqs, vocab, verbatim_tracker, instrument_catalog):
        - phrases: List of detected phrases
        - token_seqs: Token sequences for each text span (with masking state)
        - vocab: Vocabulary mapping
        - verbatim_tracker: VerbatimTracker for lemma→variants lookup
        - instrument_catalog: InstrumentCatalog if extract_instruments=True, else None
    """
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

    # Stage 2: Iterative descending k-mer mining
    for k in range(config.k_max, config.k_min - 1, -1):
        logger.info(f"Processing k={k}")

        # Count k-mers in unmasked regions
        kmer_counts = count_kmers_with_masking(token_seqs, k, config.freq_min)
        logger.info(f"  Found {len(kmer_counts)} frequent k-mers")

        if not kmer_counts:
            continue

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

    # Stage 7: Subsumption filtering (deferred to future enhancement)
    # from utils.subsumption_filter import subsumption_filter
    # filtered_phrases = subsumption_filter(all_phrases)
    # logger.info(f"After subsumption filter: {len(filtered_phrases)} phrases (removed {len(all_phrases) - len(filtered_phrases)})")

    logger.info(f"Total phrases detected: {len(all_phrases)}")
    return all_phrases, token_seqs, vocab, verbatim_tracker, instrument_catalog


def extract_instruments_only(items: List[CDEItem], config: MinerConfig):
    """
    Phase 1 mode: extract instrument patterns only, without k-mer mining.

    This is a lightweight alternative to mine_phrases() for the two-phase workflow:
    1. Phase 1: Extract instruments with lower min_tinyids threshold for discovery
    2. User curates instruments_verbatim.tsv (remove false positives)
    3. Phase 2: Run full phrase mining with curated instrument list for pre-masking

    Args:
        items: List of CDEItem objects to process
        config: Mining configuration (uses extract_instruments, min_instrument_words)

    Returns:
        InstrumentCatalog with detected instrument patterns (or None if disabled)
    """
    from utils.instrument_extractor import InstrumentExtractor, InstrumentCatalog
    from utils.phrase_extraction import tokenize_text_with_positions

    extractor = InstrumentExtractor(min_name_words=config.min_instrument_words)
    catalog = InstrumentCatalog()

    for item in items:
        if not item.tinyId:
            continue

        # Extract text spans from specified fields
        text_spans = extract_field_texts(item, config.field_names)

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
            if config.lemmatize:
                lemmas = make_lemma(tokens_lower, config.remove_stopwords, STOPWORDS)

                # Build lemma→original mapping for verbatim recovery
                # Note: After stopword removal, lists may have different lengths
                # We need to track which tokens were kept
                if config.remove_stopwords:
                    # Re-align: filter original_tokens and char_offsets to match lemmas
                    stopwords_lower = {s.lower() for s in STOPWORDS}
                    kept_indices = [i for i, t in enumerate(tokens_lower) if t not in stopwords_lower]
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
                        start, end = match.token_span
                        instrument_key = f"__INSTRUMENT__:{match.instrument_name}"
                        for i in range(start, min(end, len(mask_owner))):
                            mask_owner[i] = instrument_key

            # Pre-mask curated instrument patterns from --instrument-list
            # These are verbatim strings to find and mask in the original text
            if config.instrument_patterns:
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
