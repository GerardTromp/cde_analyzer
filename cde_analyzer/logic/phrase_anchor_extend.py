"""
Anchor extension using context-based bigram model.

This module extends detected anchor phrases left and right based on
context token frequencies. It uses a simplified Viterbi-lite approach
with beam search to find high-probability extensions.

The algorithm:
1. Extract left/right context windows around each phrase occurrence
2. Build bigram frequency model from contexts
3. Use beam search to extend phrases in both directions
4. Score extensions by log-likelihood and filter by threshold

Example:
    Anchor phrase: "reported outcome"
    Left context tokens: ["patient", "self", "clinician"]
    Right context tokens: ["measure", "assessment", "questionnaire"]

    Extension: "patient reported outcome measure" (if frequency supports it)
"""

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnchorExtension:
    """Extended phrase with left/right extensions"""
    original_phrase: object  # Phrase object
    left_extension: List[int]   # Token IDs to prepend
    right_extension: List[int]  # Token IDs to append
    extended_text: str          # Full extended phrase text
    score: float                # Log-likelihood score
    support: int                # Number of occurrences supporting this extension


@dataclass
class ExtensionConfig:
    """Configuration for anchor extension"""
    context_window: int = 3        # Tokens to look at on each side
    beam_width: int = 5            # Beam search width
    max_extension: int = 3         # Maximum tokens to extend in each direction
    min_support: int = 2           # Minimum occurrences for extension
    min_score_threshold: float = -5.0  # Minimum log-likelihood score


def extend_anchors(phrases, token_seqs, vocab, config) -> List[AnchorExtension]:
    """
    Extend anchor phrases using context-based bigram model.

    For each phrase, examines context windows around all occurrences
    and attempts to extend left and right based on token frequencies.

    Args:
        phrases: List of Phrase objects
        token_seqs: List of TokenSeq objects
        vocab: Vocabulary object
        config: MinerConfig object

    Returns:
        List of AnchorExtension objects for successfully extended phrases
    """
    if config.skip_anchor:
        logger.info("Anchor extension skipped (--skip-anchor)")
        return []

    ext_config = ExtensionConfig()
    extensions = []

    # Build token sequence lookup by (tinyId, field_path) for fast access
    seq_lookup = build_seq_lookup(token_seqs)

    logger.info(f"Attempting anchor extension for {len(phrases)} phrases")

    for phrase in phrases:
        # Extract contexts for all occurrences of this phrase
        left_contexts, right_contexts = extract_phrase_contexts(
            phrase, seq_lookup, ext_config.context_window
        )

        if not left_contexts and not right_contexts:
            continue

        # Build bigram models for left and right contexts
        left_bigrams = build_context_bigrams(left_contexts, direction="left")
        right_bigrams = build_context_bigrams(right_contexts, direction="right")

        # Attempt extension in both directions
        left_ext = extend_direction(
            phrase.token_ids, left_bigrams, ext_config, direction="left"
        )
        right_ext = extend_direction(
            phrase.token_ids, right_bigrams, ext_config, direction="right"
        )

        # Only keep if we found meaningful extensions
        if left_ext or right_ext:
            left_tokens = left_ext[0] if left_ext else []
            right_tokens = right_ext[0] if right_ext else []
            left_score = left_ext[1] if left_ext else 0.0
            right_score = right_ext[1] if right_ext else 0.0
            support = left_ext[2] if left_ext else (right_ext[2] if right_ext else 0)

            # Build extended text
            all_tokens = list(left_tokens) + list(phrase.token_ids) + list(right_tokens)
            extended_text = " ".join(vocab.get_tokens(all_tokens))

            extensions.append(AnchorExtension(
                original_phrase=phrase,
                left_extension=list(left_tokens),
                right_extension=list(right_tokens),
                extended_text=extended_text,
                score=left_score + right_score,
                support=support
            ))

    logger.info(f"Extended {len(extensions)} phrases via anchor extension")
    return extensions


def build_seq_lookup(token_seqs) -> Dict[Tuple[str, str], object]:
    """
    Build lookup from (tinyId, field_path) to TokenSeq.

    Args:
        token_seqs: List of TokenSeq objects

    Returns:
        Dict mapping (tinyId, field_path) to TokenSeq
    """
    lookup = {}
    for seq in token_seqs:
        key = (seq.cde_ref.tinyId, seq.cde_ref.field_path)
        lookup[key] = seq
    return lookup


def extract_phrase_contexts(phrase, seq_lookup, context_window: int) -> Tuple[List[List[int]], List[List[int]]]:
    """
    Extract left and right context windows for all occurrences of a phrase.

    Args:
        phrase: Phrase object with occurrences
        seq_lookup: Dict mapping (tinyId, field_path) to TokenSeq
        context_window: Number of tokens to extract on each side

    Returns:
        Tuple of (left_contexts, right_contexts) where each is a list of token lists
    """
    left_contexts = []
    right_contexts = []

    for occ in phrase.occurrences:
        key = (occ.tinyId, occ.field_path)
        seq = seq_lookup.get(key)
        if seq is None:
            continue

        start_idx, end_idx = occ.token_span

        # Extract left context (reversed so nearest token is first)
        left_start = max(0, start_idx - context_window)
        if left_start < start_idx:
            left_ctx = list(reversed(seq.tokens[left_start:start_idx]))
            left_contexts.append(left_ctx)

        # Extract right context
        right_end = min(len(seq.tokens), end_idx + context_window)
        if end_idx < right_end:
            right_ctx = seq.tokens[end_idx:right_end]
            right_contexts.append(right_ctx)

    return left_contexts, right_contexts


def build_context_bigrams(contexts: List[List[int]], direction: str) -> Dict[Tuple[int, int], int]:
    """
    Build bigram frequency model from context lists.

    For left direction: bigrams are (context_token, phrase_boundary)
    For right direction: bigrams are (phrase_boundary, context_token)

    Args:
        contexts: List of context token lists
        direction: "left" or "right"

    Returns:
        Dict mapping (token1, token2) to frequency count
    """
    bigrams = defaultdict(int)

    # Special boundary token (represented as -1)
    BOUNDARY = -1

    for ctx in contexts:
        if not ctx:
            continue

        # First token connects to phrase boundary
        if direction == "left":
            # Left context: token -> boundary
            bigrams[(ctx[0], BOUNDARY)] += 1
        else:
            # Right context: boundary -> token
            bigrams[(BOUNDARY, ctx[0])] += 1

        # Internal bigrams
        for i in range(len(ctx) - 1):
            if direction == "left":
                # Left context is reversed, so bigram order is ctx[i+1] -> ctx[i]
                bigrams[(ctx[i + 1], ctx[i])] += 1
            else:
                bigrams[(ctx[i], ctx[i + 1])] += 1

    return dict(bigrams)


def extend_direction(
    phrase_tokens: Tuple[int, ...],
    bigrams: Dict[Tuple[int, int], int],
    config: ExtensionConfig,
    direction: str
) -> Optional[Tuple[List[int], float, int]]:
    """
    Extend phrase in one direction using beam search.

    Args:
        phrase_tokens: Original phrase token IDs
        bigrams: Bigram frequency model
        config: Extension configuration
        direction: "left" or "right"

    Returns:
        Tuple of (extension_tokens, score, support) or None if no good extension
    """
    if not bigrams:
        return None

    BOUNDARY = -1

    # Calculate total counts for probability estimation
    total_counts = sum(bigrams.values())
    if total_counts == 0:
        return None

    # Find tokens that connect to phrase boundary
    if direction == "left":
        # Left: look for (token, BOUNDARY) patterns
        candidates = [(t1, count) for (t1, t2), count in bigrams.items()
                     if t2 == BOUNDARY and count >= config.min_support]
    else:
        # Right: look for (BOUNDARY, token) patterns
        candidates = [(t2, count) for (t1, t2), count in bigrams.items()
                     if t1 == BOUNDARY and count >= config.min_support]

    if not candidates:
        return None

    # Sort by frequency
    candidates.sort(key=lambda x: -x[1])

    # Take best candidate (simplified - could use beam search for longer extensions)
    best_token, best_count = candidates[0]

    # Calculate log-likelihood score
    prob = best_count / total_counts
    score = math.log(prob) if prob > 0 else float('-inf')

    if score < config.min_score_threshold:
        return None

    # For now, only extend by one token (could iterate for longer extensions)
    extension = [best_token]

    return (extension, score, best_count)


def extend_with_beam_search(
    phrase_tokens: Tuple[int, ...],
    bigrams: Dict[Tuple[int, int], int],
    config: ExtensionConfig,
    direction: str
) -> List[Tuple[List[int], float, int]]:
    """
    Extended beam search for multi-token extensions.

    This is a more sophisticated version that can extend multiple tokens.

    Args:
        phrase_tokens: Original phrase token IDs
        bigrams: Bigram frequency model
        config: Extension configuration
        direction: "left" or "right"

    Returns:
        List of (extension_tokens, score, support) tuples, sorted by score
    """
    if not bigrams:
        return []

    BOUNDARY = -1
    total_counts = sum(bigrams.values())
    if total_counts == 0:
        return []

    # Beam: list of (tokens, score, min_support)
    beam = [([], 0.0, float('inf'))]

    for step in range(config.max_extension):
        new_beam = []

        for tokens, score, min_sup in beam:
            # Find next token candidates
            if not tokens:
                # First extension - connect to boundary
                if direction == "left":
                    candidates = [(t1, c) for (t1, t2), c in bigrams.items()
                                 if t2 == BOUNDARY]
                else:
                    candidates = [(t2, c) for (t1, t2), c in bigrams.items()
                                 if t1 == BOUNDARY]
            else:
                # Continue from last token
                last_token = tokens[-1] if direction == "right" else tokens[0]
                if direction == "left":
                    candidates = [(t1, c) for (t1, t2), c in bigrams.items()
                                 if t2 == last_token]
                else:
                    candidates = [(t2, c) for (t1, t2), c in bigrams.items()
                                 if t1 == last_token]

            # Score and filter candidates
            for next_token, count in candidates:
                if count < config.min_support:
                    continue

                prob = count / total_counts
                next_score = score + (math.log(prob) if prob > 0 else float('-inf'))

                if next_score < config.min_score_threshold:
                    continue

                if direction == "left":
                    new_tokens = [next_token] + tokens
                else:
                    new_tokens = tokens + [next_token]

                new_min_sup = min(min_sup, count)
                new_beam.append((new_tokens, next_score, new_min_sup))

        if not new_beam:
            break

        # Keep top beam_width candidates
        new_beam.sort(key=lambda x: -x[1])
        beam = new_beam[:config.beam_width]

        # Also keep partial results
        beam.append(([], 0.0, float('inf')))  # Allow stopping early

    # Filter and return results
    results = [(tokens, score, int(min_sup))
               for tokens, score, min_sup in beam
               if tokens and score >= config.min_score_threshold]

    results.sort(key=lambda x: -x[1])
    return results
