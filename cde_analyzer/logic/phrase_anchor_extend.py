"""
Lightweight anchor extension using atom-based bigram model.

This module is a placeholder for future implementation (Phase 7+).
Anchor extension uses Viterbi-lite beam search to extend detected phrases
left and right based on context bigram probabilities.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


def extend_anchors(phrases, token_seqs, vocab, config):
    """
    Extend anchor phrases using atom-based bigram model.

    This feature is deferred to future implementation (Phase 7+).

    Args:
        phrases: List of Phrase objects
        token_seqs: List of TokenSeq objects
        vocab: Vocabulary object
        config: MinerConfig object

    Returns:
        Empty list (feature not yet implemented)
    """
    logger.info("Anchor extension is not yet implemented (deferred to Phase 7+)")
    return []


# Future implementation (Phase 7+):
# 1. extract_atom_contexts() - Extract left/right context windows
# 2. build_atom_bigram_model() - Compute bigram probabilities
# 3. viterbi_extend_left() - Beam search for left extension
# 4. viterbi_extend_right() - Beam search for right extension
