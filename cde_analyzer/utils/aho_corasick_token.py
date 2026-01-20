"""
Token-based Aho-Corasick automaton for efficient multi-pattern matching.

This module implements a token-level (not character-level) Aho-Corasick automaton
for finding multiple phrase patterns simultaneously in token sequences. This is
used for efficient phrase masking in the phrase_miner pipeline.

Time Complexity:
- Construction: O(sum of pattern lengths)
- Matching: O(text length + number of matches)

This is significantly faster than naive O(n*m*k) matching where:
- n = text length
- m = number of patterns
- k = average pattern length
"""

from typing import List, Dict, Tuple, Optional
from collections import deque


class ACNode:
    """
    Aho-Corasick automaton node for token sequences.

    Each node represents a state in the automaton, with:
    - goto: Transition function (token_id → next state)
    - fail: Failure link for when no transition exists
    - output: List of patterns that end at this state
    """

    def __init__(self):
        self.goto: Dict[int, 'ACNode'] = {}  # token_id -> next node
        self.fail: Optional['ACNode'] = None  # Failure link
        self.output: List[Tuple[str, int]] = []  # [(pattern_id, pattern_length), ...]


class AhoCorasickAutomaton:
    """
    Aho-Corasick automaton for token sequences.

    Unlike traditional character-based AC automata, this operates on
    integer token IDs, making it suitable for phrase pattern matching
    after tokenization.

    Example:
        automaton = AhoCorasickAutomaton()
        automaton.add_pattern("phrase_001", [45, 23, 78])  # Token IDs
        automaton.add_pattern("phrase_002", [23, 78, 12])
        automaton.build_failure_links()

        matches = automaton.search([10, 45, 23, 78, 12, 99])
        # Returns: [("phrase_001", 1, 4), ("phrase_002", 2, 5)]
    """

    def __init__(self):
        self.root = ACNode()
        self._built = False

    def add_pattern(self, pattern_id: str, tokens: List[int]):
        """
        Add a pattern (token sequence) to the automaton.

        Must be called before build_failure_links().

        Args:
            pattern_id: Unique identifier for this pattern (e.g., phrase_id)
            tokens: List of token IDs representing the pattern
        """
        if self._built:
            raise RuntimeError("Cannot add patterns after building failure links")

        node = self.root
        for token in tokens:
            if token not in node.goto:
                node.goto[token] = ACNode()
            node = node.goto[token]
        node.output.append((pattern_id, len(tokens)))

    def build_failure_links(self):
        """
        Build failure links using BFS traversal.

        Must be called after all patterns are added and before searching.
        """
        if self._built:
            return

        queue = deque()

        # Level 1: Direct children of root have failure links to root
        for child in self.root.goto.values():
            child.fail = self.root
            queue.append(child)

        # BFS to build remaining failure links
        while queue:
            current = queue.popleft()

            for token, child in current.goto.items():
                queue.append(child)

                # Find failure link by following parent's failure chain
                fail_node = current.fail
                while fail_node is not None and token not in fail_node.goto:
                    fail_node = fail_node.fail

                if fail_node is not None:
                    child.fail = fail_node.goto[token]
                else:
                    child.fail = self.root

                # Merge output from failure node (suffix patterns)
                if child.fail.output:
                    child.output = child.output + child.fail.output

        self._built = True

    def search(self, text_tokens: List[int]) -> List[Tuple[str, int, int]]:
        """
        Find all pattern matches in a token sequence.

        Args:
            text_tokens: Token sequence to search

        Returns:
            List of (pattern_id, start_idx, end_idx) tuples where:
            - pattern_id: The identifier of the matched pattern
            - start_idx: Starting index (inclusive) in text_tokens
            - end_idx: Ending index (exclusive) in text_tokens
        """
        if not self._built:
            self.build_failure_links()

        matches = []
        node = self.root

        for i, token in enumerate(text_tokens):
            # Follow failure links until we find a match or reach root
            while node is not self.root and token not in node.goto:
                node = node.fail

            # Transition to next state
            if token in node.goto:
                node = node.goto[token]
            else:
                node = self.root

            # Record all matches (node.output contains all patterns ending here)
            for pattern_id, pattern_length in node.output:
                end_idx = i + 1  # Exclusive
                start_idx = end_idx - pattern_length
                if start_idx >= 0:
                    matches.append((pattern_id, start_idx, end_idx))

        return matches


def build_automaton(patterns: Dict[str, List[int]]) -> AhoCorasickAutomaton:
    """
    Build Aho-Corasick automaton from pattern dictionary.

    Convenience function to create and configure an automaton.

    Args:
        patterns: Dict mapping pattern_id to token_id list

    Returns:
        Compiled automaton ready for searching

    Example:
        patterns = {
            "phrase_001": [45, 23, 78],
            "phrase_002": [23, 78, 12],
        }
        automaton = build_automaton(patterns)
        matches = automaton.search([10, 45, 23, 78, 12, 99])
    """
    automaton = AhoCorasickAutomaton()

    for pattern_id, tokens in patterns.items():
        automaton.add_pattern(pattern_id, tokens)

    automaton.build_failure_links()
    return automaton


def match_patterns(automaton: AhoCorasickAutomaton, text_tokens: List[int],
                   patterns: Optional[Dict[str, List[int]]] = None) -> List[Tuple[str, int, int]]:
    """
    Find all pattern matches in text token sequence.

    Wrapper around automaton.search() for compatibility.

    Args:
        automaton: Compiled Aho-Corasick automaton
        text_tokens: Token sequence to search
        patterns: Original patterns dict (unused, for API compatibility)

    Returns:
        List of (pattern_id, start_idx, end_idx) tuples
    """
    return automaton.search(text_tokens)
