"""
Hybrid verbatim text recovery for phrase_miner action.

Provides two mechanisms for recovering original (non-lemmatized) text:
1. Position-based tracking: Exact verbatim text per occurrence
2. Lemma → variants dictionary: PrefixTrie for fast lookup and analysis

The PrefixTrie uses a configurable prefix length (default 2 characters) to
organize variants, enabling O(k) lookup where k = prefix length.
"""

from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


class PrefixTrie:
    """
    Trie for fast prefix-based variant lookup.

    Organizes variants by their first N characters for efficient lookup
    when reconstructing verbatim text from lemmas.
    """

    def __init__(self):
        self.children: Dict[str, 'PrefixTrie'] = {}
        self.variants: Set[str] = set()

    def insert(self, variant: str, prefix_len: int = 2):
        """
        Insert variant with first N characters as path.

        Args:
            variant: Original token text to store
            prefix_len: Number of characters to use as trie path
        """
        if len(variant) < prefix_len:
            prefix = variant.lower()
        else:
            prefix = variant[:prefix_len].lower()

        node = self
        for char in prefix:
            if char not in node.children:
                node.children[char] = PrefixTrie()
            node = node.children[char]
        node.variants.add(variant)

    def lookup(self, prefix: str) -> Set[str]:
        """
        Find all variants matching prefix.

        Args:
            prefix: Character prefix to match

        Returns:
            Set of variants with matching prefix
        """
        prefix = prefix.lower()
        node = self
        for char in prefix:
            if char not in node.children:
                return set()
            node = node.children[char]

        # Collect all variants in subtree
        return self._collect_variants(node)

    def _collect_variants(self, node: 'PrefixTrie') -> Set[str]:
        """Recursively collect all variants from node and descendants."""
        result = set(node.variants)
        for child in node.children.values():
            result.update(self._collect_variants(child))
        return result

    def all_variants(self) -> Set[str]:
        """Get all variants stored in this trie."""
        return self._collect_variants(self)


class VerbatimTracker:
    """
    Hybrid verbatim recovery system for phrase mining.

    Tracks the relationship between lemmatized tokens and their original
    surface forms (verbatim text). Supports two use cases:

    1. Position-based: Each phrase occurrence stores its exact verbatim text
       (handled by CDERef.verbatim_text in phrase_miner.py)

    2. Lemma → variants: This class maintains a dictionary mapping each lemma
       to all observed original forms, organized in a PrefixTrie for fast
       prefix-based lookup.

    Example:
        tracker = VerbatimTracker(prefix_len=2)
        tracker.register_token("patient", "Patient")
        tracker.register_token("patient", "patients")
        tracker.register_token("patient", "PATIENT")

        # Get all variants
        variants = tracker.get_variants("patient")
        # {'Patient', 'patients', 'PATIENT'}

        # Fast prefix lookup
        variants = tracker.lookup_by_prefix("patient", "Pa")
        # {'Patient', 'patients'}  (case-insensitive prefix match)
    """

    def __init__(self, prefix_len: int = 2):
        """
        Initialize verbatim tracker.

        Args:
            prefix_len: Number of characters to use for trie prefix paths.
                       Higher values = more specific lookup but more memory.
                       Default 2 typically gives good balance.
        """
        self.prefix_len = prefix_len
        # Lemma → PrefixTrie of variants
        self.lemma_to_variants: Dict[str, PrefixTrie] = defaultdict(PrefixTrie)
        # Statistics
        self._total_variants = 0

    def register_token(self, lemma: str, original: str):
        """
        Register a lemma → original mapping.

        Args:
            lemma: Lemmatized token (typically lowercase)
            original: Original token as it appeared in source text
        """
        trie = self.lemma_to_variants[lemma]

        # Check if this variant is already registered
        existing = trie.all_variants()
        if original not in existing:
            trie.insert(original, self.prefix_len)
            self._total_variants += 1

    def get_variants(self, lemma: str) -> Set[str]:
        """
        Get all known variants for a lemma.

        Args:
            lemma: The lemmatized token

        Returns:
            Set of all original forms observed for this lemma
        """
        if lemma not in self.lemma_to_variants:
            return set()
        return self.lemma_to_variants[lemma].all_variants()

    def lookup_by_prefix(self, lemma: str, prefix: str) -> Set[str]:
        """
        Fast lookup: Get variants for lemma matching prefix.

        Useful when you have partial information about the original form
        (e.g., first few characters from context).

        Args:
            lemma: The lemmatized token
            prefix: First N characters to match (e.g., "Pa" for "Patient")

        Returns:
            Set of matching original variants
        """
        if lemma not in self.lemma_to_variants:
            return set()
        return self.lemma_to_variants[lemma].lookup(prefix)

    def get_statistics(self) -> Dict[str, float]:
        """
        Return tracker statistics.

        Returns:
            Dictionary with:
            - unique_lemmas: Number of distinct lemmas tracked
            - total_variants: Total number of variant forms
            - avg_variants_per_lemma: Average variants per lemma
        """
        unique_lemmas = len(self.lemma_to_variants)
        return {
            "unique_lemmas": unique_lemmas,
            "total_variants": self._total_variants,
            "avg_variants_per_lemma": (
                self._total_variants / unique_lemmas
                if unique_lemmas > 0 else 0.0
            )
        }

    def __len__(self) -> int:
        """Return number of unique lemmas tracked."""
        return len(self.lemma_to_variants)

    def __contains__(self, lemma: str) -> bool:
        """Check if lemma is tracked."""
        return lemma in self.lemma_to_variants
