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


def subsumption_filter(phrases: List, require_tinyid_overlap: bool = True,
                       min_subsume_coverage: float = 0.0,
                       max_orphan_tinyids: int = 999_999) -> List:
    """
    Remove phrases that are fully contained in longer phrases.

    A phrase P is subsumed by Q if:
      - P's token sequence is a contiguous subsequence of Q's
      - P and Q share at least one tinyId (if require_tinyid_overlap=True)
      - Q covers >= min_subsume_coverage of P's tinyIds (if > 0)
      - The number of P's tinyIds NOT in Q is <= max_orphan_tinyids

    The coverage check prevents a long phrase with few tinyIds from subsuming
    a shorter phrase with many tinyIds.  The orphan check prevents subsumption
    even at high coverage ratios when the absolute number of uncovered tinyIds
    is large.

    Args:
        phrases: List of Phrase objects
        require_tinyid_overlap: If True, only subsume if phrases share tinyIds
        min_subsume_coverage: Min fraction of the shorter phrase's tinyIds that
            must be covered by the longer phrase for subsumption to occur.
            0.0 = any overlap suffices (legacy). 0.5 = longer must cover >= 50%.
        max_orphan_tinyids: Max number of the shorter phrase's tinyIds that may
            be left uncovered. If orphan count exceeds this, keep both phrases.
            Default: 999999 (no limit). Set to e.g. 10 to protect large groups.

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
                if require_tinyid_overlap:
                    should, coverage, orphan_n = _check_coverage_subsumption(
                        phrase.distinct_tinyids, candidate.distinct_tinyids,
                        min_subsume_coverage, max_orphan_tinyids)
                    if should:
                        subsumed_ids.add(candidate.phrase_id)
                        logger.debug(
                            f"Subsumed: '{candidate.text}' by '{phrase.text}' "
                            f"(coverage={coverage:.0%}, orphan={orphan_n})")
                    elif coverage > 0:
                        logger.debug(
                            f"Kept: '{candidate.text}' "
                            f"(coverage={coverage:.0%}, orphan={orphan_n} "
                            f"by '{phrase.text}')")
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


def _check_coverage_subsumption(
    longer_tinyids: Set[str],
    shorter_tinyids: Set[str],
    min_subsume_coverage: float,
    max_orphan_tinyids: int,
) -> Tuple[bool, float, int]:
    """Check if a shorter phrase should be subsumed by a longer one.

    Returns (should_subsume, coverage, orphan_count).

    Fast path: when min_subsume_coverage == 0 and max_orphan_tinyids >= 999_999,
    short-circuits on first shared element (legacy behavior).
    """
    use_legacy = (min_subsume_coverage <= 0.0 and max_orphan_tinyids >= 999_999)

    if use_legacy:
        # Short-circuit: any overlap suffices
        smaller, larger = (shorter_tinyids, longer_tinyids) \
            if len(shorter_tinyids) <= len(longer_tinyids) \
            else (longer_tinyids, shorter_tinyids)
        for item in smaller:
            if item in larger:
                return (True, 1.0, 0)
        return (False, 0.0, 0)

    # Full intersection needed for coverage calculation
    overlap = longer_tinyids & shorter_tinyids
    if not overlap:
        return (False, 0.0, 0)

    n_shorter = len(shorter_tinyids)
    coverage = len(overlap) / n_shorter if n_shorter else 0.0
    orphan_n = n_shorter - len(overlap)
    should = (coverage >= min_subsume_coverage and orphan_n <= max_orphan_tinyids)
    return (should, coverage, orphan_n)


def subsumption_filter_optimized(phrases: List, require_tinyid_overlap: bool = True,
                                  min_subsume_coverage: float = 0.0,
                                  max_orphan_tinyids: int = 999_999) -> List:
    """
    Optimized subsumption filter using suffix-based indexing.

    For large phrase sets, this version uses an index to reduce comparisons.
    Falls back to simple algorithm for small sets.

    Args:
        phrases: List of Phrase objects
        require_tinyid_overlap: If True, only subsume if phrases share tinyIds
        min_subsume_coverage: Min fraction of shorter phrase's tinyIds that
            must be covered by longer phrase. See subsumption_filter().
        max_orphan_tinyids: Max uncovered tinyIds before keeping both.
            See subsumption_filter().

    Returns:
        Filtered list with subsumed phrases removed
    """
    # Use simple algorithm for small sets
    if len(phrases) < 100:
        return subsumption_filter(phrases, require_tinyid_overlap,
                                  min_subsume_coverage, max_orphan_tinyids)

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
                        should, _, _ = _check_coverage_subsumption(
                            phrase.distinct_tinyids, candidate.distinct_tinyids,
                            min_subsume_coverage, max_orphan_tinyids)
                        if should:
                            subsumed_ids.add(candidate.phrase_id)
                    else:
                        subsumed_ids.add(candidate.phrase_id)

        keep.append(phrase)

    logger.info(f"Subsumption filter (optimized): {len(phrases)} -> {len(keep)} phrases "
                f"(removed {len(subsumed_ids)})")

    return keep
