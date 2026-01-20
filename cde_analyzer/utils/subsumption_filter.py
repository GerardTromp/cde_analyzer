"""
Subsumption filtering for phrase mining.

Removes shorter phrases that are fully contained within longer phrases,
reducing redundancy in the output. A phrase P is subsumed by phrase Q if:
1. P's token sequence is a contiguous subsequence of Q's
2. P and Q share at least one tinyId (document overlap)

This ensures we keep the most informative (longest) phrases while
eliminating redundant shorter fragments.

Example:
    If we detect both "patient reported" and "patient reported outcome",
    and they occur in the same documents, "patient reported" is subsumed
    by the longer phrase and can be removed.
"""

from typing import List, Set, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def subsumption_filter(phrases: List, require_tinyid_overlap: bool = True) -> List:
    """
    Remove phrases that are fully contained in longer phrases.

    A phrase P is subsumed by Q if:
      - P's token sequence is a contiguous subsequence of Q's
      - P and Q share at least one tinyId (if require_tinyid_overlap=True)

    Args:
        phrases: List of Phrase objects
        require_tinyid_overlap: If True, only subsume if phrases share tinyIds

    Returns:
        Filtered list with subsumed phrases removed
    """
    if not phrases:
        return []

    # Sort by length descending (longer phrases first)
    sorted_phrases = sorted(phrases, key=lambda p: len(p.token_ids), reverse=True)

    keep = []
    subsumed_ids: Set[str] = set()

    # Build index of token sequences for faster lookup
    # Map from first token to list of (phrase, token_tuple)
    phrase_index: Dict[int, List[Tuple[object, Tuple[int, ...]]]] = {}
    for phrase in sorted_phrases:
        first_token = phrase.token_ids[0] if phrase.token_ids else None
        if first_token is not None:
            if first_token not in phrase_index:
                phrase_index[first_token] = []
            phrase_index[first_token].append((phrase, tuple(phrase.token_ids)))

    for i, phrase in enumerate(sorted_phrases):
        if phrase.phrase_id in subsumed_ids:
            continue

        phrase_tokens = tuple(phrase.token_ids)
        phrase_len = len(phrase_tokens)

        # Check if this phrase subsumes any later (shorter) phrases
        for j in range(i + 1, len(sorted_phrases)):
            candidate = sorted_phrases[j]

            if candidate.phrase_id in subsumed_ids:
                continue

            candidate_tokens = tuple(candidate.token_ids)
            candidate_len = len(candidate_tokens)

            # Skip if candidate is same length or longer (can't be subsumed)
            if candidate_len >= phrase_len:
                continue

            # Check containment
            if is_contained(candidate_tokens, phrase_tokens):
                # Check tinyId overlap if required
                if require_tinyid_overlap:
                    if has_tinyid_overlap(candidate.distinct_tinyids, phrase.distinct_tinyids):
                        subsumed_ids.add(candidate.phrase_id)
                        logger.debug(f"Subsumed: '{candidate.text}' by '{phrase.text}'")
                else:
                    subsumed_ids.add(candidate.phrase_id)
                    logger.debug(f"Subsumed: '{candidate.text}' by '{phrase.text}'")

        keep.append(phrase)

    logger.info(f"Subsumption filter: {len(phrases)} -> {len(keep)} phrases "
                f"(removed {len(subsumed_ids)})")

    return keep


def is_contained(short: Tuple[int, ...], long: Tuple[int, ...]) -> bool:
    """
    Check if short token sequence is a contiguous subsequence of long.

    Args:
        short: Potential subsequence (tuple of token IDs)
        long: Sequence to search in (tuple of token IDs)

    Returns:
        True if short appears contiguously in long
    """
    n, m = len(long), len(short)
    if m > n:
        return False
    if m == 0:
        return True

    # Sliding window search
    for i in range(n - m + 1):
        if long[i:i + m] == short:
            return True
    return False


def has_tinyid_overlap(set1: Set[str], set2: Set[str]) -> bool:
    """
    Check if two tinyId sets have non-empty intersection.

    Args:
        set1: First set of tinyIds
        set2: Second set of tinyIds

    Returns:
        True if sets share at least one element
    """
    # Use smaller set for iteration (optimization)
    if len(set1) > len(set2):
        set1, set2 = set2, set1

    for item in set1:
        if item in set2:
            return True
    return False


def subsumption_filter_optimized(phrases: List, require_tinyid_overlap: bool = True) -> List:
    """
    Optimized subsumption filter using suffix-based indexing.

    For large phrase sets, this version uses an index to reduce comparisons.
    Falls back to simple algorithm for small sets.

    Args:
        phrases: List of Phrase objects
        require_tinyid_overlap: If True, only subsume if phrases share tinyIds

    Returns:
        Filtered list with subsumed phrases removed
    """
    # Use simple algorithm for small sets
    if len(phrases) < 100:
        return subsumption_filter(phrases, require_tinyid_overlap)

    if not phrases:
        return []

    # Sort by length descending
    sorted_phrases = sorted(phrases, key=lambda p: len(p.token_ids), reverse=True)

    # Build suffix index: map (first_n_tokens) -> list of phrases starting with those tokens
    # This allows faster lookup of potential container phrases
    suffix_index: Dict[Tuple[int, ...], List] = {}
    prefix_len = 3  # Index on first 3 tokens

    for phrase in sorted_phrases:
        tokens = tuple(phrase.token_ids)
        if len(tokens) >= prefix_len:
            prefix = tokens[:prefix_len]
        else:
            prefix = tokens

        if prefix not in suffix_index:
            suffix_index[prefix] = []
        suffix_index[prefix].append(phrase)

    keep = []
    subsumed_ids: Set[str] = set()

    for phrase in sorted_phrases:
        if phrase.phrase_id in subsumed_ids:
            continue

        phrase_tokens = tuple(phrase.token_ids)
        phrase_len = len(phrase_tokens)

        # Check all possible starting positions within this phrase
        # that could match shorter phrases
        for start in range(phrase_len):
            remaining = phrase_tokens[start:]
            if len(remaining) >= prefix_len:
                prefix = remaining[:prefix_len]
            else:
                prefix = remaining

            # Look up candidates that start with this prefix
            candidates = suffix_index.get(prefix, [])
            for candidate in candidates:
                if candidate.phrase_id == phrase.phrase_id:
                    continue
                if candidate.phrase_id in subsumed_ids:
                    continue

                candidate_tokens = tuple(candidate.token_ids)
                if len(candidate_tokens) >= phrase_len:
                    continue

                # Check if candidate is contained starting at this position
                if remaining[:len(candidate_tokens)] == candidate_tokens:
                    if require_tinyid_overlap:
                        if has_tinyid_overlap(candidate.distinct_tinyids, phrase.distinct_tinyids):
                            subsumed_ids.add(candidate.phrase_id)
                    else:
                        subsumed_ids.add(candidate.phrase_id)

        keep.append(phrase)

    logger.info(f"Subsumption filter (optimized): {len(phrases)} -> {len(keep)} phrases "
                f"(removed {len(subsumed_ids)})")

    return keep
