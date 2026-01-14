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


@dataclass
class CDERef:
    """Reference to source CDE document and field path"""
    tinyId: str
    field_path: str           # e.g., "designations[0].designation"
    token_span: Tuple[int, int]  # (start_tok, end_tok) in token sequence


@dataclass
class TokenSeq:
    """Token sequence with masking state"""
    tokens: List[int]         # Vocab token IDs
    cde_ref: CDERef
    mask_owner: List[Optional[str]]  # phrase_id that owns each token (None = unmasked)


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
    skip_debruijn: bool = True  # Defer to future enhancement
    skip_anchor: bool = True    # Defer to future enhancement
    generate_histograms: bool = False


def mine_phrases(items: List[CDEItem], config: MinerConfig) -> Tuple[List[Phrase], List[TokenSeq], Vocabulary]:
    """
    Main phrase mining pipeline.

    Args:
        items: List of CDEItem objects to process
        config: Mining configuration

    Returns:
        Tuple of (phrases, token_seqs, vocab):
        - phrases: List of detected phrases
        - token_seqs: Token sequences for each text span (with masking state)
        - vocab: Vocabulary mapping
    """
    # Stage 1: Extract and tokenize text spans from CDE fields
    token_seqs, vocab = extract_token_sequences(items, config)
    logger.info(f"Extracted {len(token_seqs)} token sequences, vocab size {len(vocab)}")

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

        # Stage 3: De Bruijn graph extension (deferred to future enhancement)
        # if not config.skip_debruijn:
        #     from utils.debruijn_graph import debruijn_extend_bin
        #     kmer_counts = debruijn_extend_bin(kmer_counts, vocab, config)

        # Stage 4: Convert k-mers to phrases
        new_phrases = []
        for kmer_count in kmer_counts:
            phrase = kmer_count_to_phrase(kmer_count, phrase_id_counter, k, vocab)
            phrase_id_counter += 1

            # Stage 5: Filter by tinyId support
            if len(phrase.distinct_tinyids) >= config.min_distinct_tinyids:
                new_phrases.append(phrase)

        all_phrases.extend(new_phrases)
        logger.info(f"  Added {len(new_phrases)} phrases (filtered by min_tinyids={config.min_distinct_tinyids})")

        # Stage 6: Mask detected phrases (naive implementation for Phase 1-3)
        mask_phrases_naive(token_seqs, new_phrases)

    # Stage 7: Subsumption filtering (deferred to future enhancement)
    # from utils.subsumption_filter import subsumption_filter
    # filtered_phrases = subsumption_filter(all_phrases)
    # logger.info(f"After subsumption filter: {len(filtered_phrases)} phrases (removed {len(all_phrases) - len(filtered_phrases)})")

    logger.info(f"Total phrases detected: {len(all_phrases)}")
    return all_phrases, token_seqs, vocab


def extract_token_sequences(items: List[CDEItem], config: MinerConfig) -> Tuple[List[TokenSeq], Vocabulary]:
    """
    Extract text from specified fields, tokenize, lemmatize, build vocabulary.

    Args:
        items: List of CDEItem objects
        config: Mining configuration

    Returns:
        Tuple of (token_seqs, vocab):
        - token_seqs: List of TokenSeq objects
        - vocab: Vocabulary object
    """
    from utils.phrase_extraction import tokenize_text, make_lemma, STOPWORDS

    vocab = Vocabulary()
    token_seqs = []

    for item in items:
        if not item.tinyId:
            continue

        # Extract text spans from specified fields
        text_spans = extract_field_texts(item, config.field_names)

        for field_path, text in text_spans:
            # Tokenize (reuse existing utility)
            tokens_str = tokenize_text(text)
            if not tokens_str:
                continue

            # Lemmatize if configured
            if config.lemmatize:
                tokens_str = make_lemma(tokens_str, config.remove_stopwords, STOPWORDS)

            if not tokens_str:  # Skip if no tokens remain after lemmatization
                continue

            # Convert to vocab IDs
            token_ids = [vocab.add_token(t) for t in tokens_str]

            # Create TokenSeq with unmasked state
            cde_ref = CDERef(
                tinyId=item.tinyId,
                field_path=field_path,
                token_span=(0, len(token_ids))
            )
            token_seqs.append(TokenSeq(
                tokens=token_ids,
                cde_ref=cde_ref,
                mask_owner=[None] * len(token_ids)
            ))

    return token_seqs, vocab


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


def count_kmers_with_masking(token_seqs: List[TokenSeq], k: int, freq_min: int) -> List[KmerCount]:
    """
    Count k-mers in unmasked regions only.

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

                # Record occurrence location
                occ = CDERef(
                    tinyId=seq.cde_ref.tinyId,
                    field_path=seq.cde_ref.field_path,
                    token_span=(i, i+k)
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

    This is a simple implementation for Phase 1-3.
    Future enhancement: Replace with Aho-Corasick for O(n+m) performance.

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


def kmer_count_to_phrase(kmer_count: KmerCount, phrase_id: int, k: int, vocab: Vocabulary) -> Phrase:
    """
    Convert KmerCount to Phrase object.

    Args:
        kmer_count: KmerCount object
        phrase_id: Sequential phrase ID number
        k: K-mer length
        vocab: Vocabulary for text conversion

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
        extension_method="kmer"
    )
