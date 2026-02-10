"""
Bottom-up k-mer analysis for phrase family discovery.

Implements three independent tree-building strategies:
1. Prefix tree (trie): Groups phrases by shared beginnings
2. Suffix tree (reversed trie): Groups phrases by shared endings
3. Infix index (inverted index): Groups phrases by shared internal k-mers

Each strategy uses bottom-up k-mer construction:
- Start from k_min (default: 2 tokens)
- Count k-mer frequencies across all phrases
- Extend upward while maintaining minimum family size
- Track which phrases contain each pattern

Frequency determines the "best" family assignment when a phrase
matches multiple patterns across different trees.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, TYPE_CHECKING
from collections import defaultdict
import logging

if TYPE_CHECKING:
    from actions.phrase_grouper.run import PhraseRecord

logger = logging.getLogger(__name__)


@dataclass
class GrouperConfig:
    """Configuration for phrase grouper algorithm"""
    k_min: int = 3
    k_max: int = 10
    min_family_size: int = 3
    min_pattern_freq: int = 3
    min_content_words: int = 1  # Minimum non-stopword tokens in pattern
    assignment_strategy: str = "frequency"  # frequency, longest, all


# Common English stopwords for filtering low-content patterns
STOPWORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'else',
    'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'from',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
    'will', 'would', 'could', 'should', 'may', 'might', 'must',
    'that', 'which', 'who', 'whom', 'whose', 'this', 'these', 'those',
    'it', 'its', 'as', 'so', 'than', 'such', 'no', 'not', 'only',
    'own', 'same', 'too', 'very', 'just', 'also', 'now', 'here',
    'there', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
    'both', 'few', 'more', 'most', 'other', 'some', 'any', 'can',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'under', 'over', 'out', 'up', 'down', 'about', 'again',
})


def count_content_words(tokens: Tuple[str, ...]) -> int:
    """Count non-stopword tokens in a pattern."""
    return sum(1 for t in tokens if t.lower() not in STOPWORDS)


@dataclass
class TrieNode:
    """Node in prefix/suffix trie"""
    children: Dict[str, 'TrieNode'] = field(default_factory=dict)
    phrase_ids: Set[str] = field(default_factory=set)
    tinyids: Set[str] = field(default_factory=set)
    count: int = 0
    depth: int = 0


@dataclass
class PatternInfo:
    """Information about a discovered pattern"""
    pattern: str  # The k-mer pattern as space-joined tokens
    tokens: Tuple[str, ...]  # The tokens
    phrase_ids: Set[str]  # Phrases containing this pattern
    tinyids: Set[str]  # Union of tinyIds from matching phrases
    frequency: int  # Total occurrences
    k: int  # Length in tokens


def build_prefix_tree(
    phrases: List['PhraseRecord'],
    config: GrouperConfig
) -> Dict[str, PatternInfo]:
    """
    Build prefix tree (trie) from phrases.

    Inserts each phrase into a trie, tracking which phrases share
    each prefix. Returns patterns that meet minimum family size.

    Args:
        phrases: List of PhraseRecord objects
        config: Grouper configuration

    Returns:
        Dict mapping pattern string to PatternInfo
    """
    root = TrieNode()

    # Insert all phrases into trie
    for phrase in phrases:
        node = root
        for i, token in enumerate(phrase.tokens):
            if i >= config.k_max:
                break
            if token not in node.children:
                node.children[token] = TrieNode(depth=i + 1)
            node = node.children[token]
            node.phrase_ids.add(phrase.phrase_id)
            node.tinyids.update(phrase.tinyids)
            node.count += 1

    # Extract patterns meeting criteria
    patterns = {}

    def traverse(node: TrieNode, path: List[str]):
        if node.depth >= config.k_min and len(node.phrase_ids) >= config.min_family_size:
            pattern_str = " ".join(path)
            patterns[pattern_str] = PatternInfo(
                pattern=pattern_str,
                tokens=tuple(path),
                phrase_ids=node.phrase_ids.copy(),
                tinyids=node.tinyids.copy(),
                frequency=node.count,
                k=len(path),
            )

        for token, child in node.children.items():
            traverse(child, path + [token])

    traverse(root, [])
    logger.debug(f"Prefix tree: {len(patterns)} patterns found")
    return patterns


def build_suffix_tree(
    phrases: List['PhraseRecord'],
    config: GrouperConfig
) -> Dict[str, PatternInfo]:
    """
    Build suffix tree (reversed trie) from phrases.

    Inserts each phrase in reverse order, tracking which phrases
    share each suffix.

    Args:
        phrases: List of PhraseRecord objects
        config: Grouper configuration

    Returns:
        Dict mapping pattern string to PatternInfo
    """
    root = TrieNode()

    # Insert all phrases into trie (reversed)
    for phrase in phrases:
        node = root
        reversed_tokens = list(reversed(phrase.tokens))
        for i, token in enumerate(reversed_tokens):
            if i >= config.k_max:
                break
            if token not in node.children:
                node.children[token] = TrieNode(depth=i + 1)
            node = node.children[token]
            node.phrase_ids.add(phrase.phrase_id)
            node.tinyids.update(phrase.tinyids)
            node.count += 1

    # Extract patterns meeting criteria
    patterns = {}

    def traverse(node: TrieNode, path: List[str]):
        if node.depth >= config.k_min and len(node.phrase_ids) >= config.min_family_size:
            # Reverse path back to normal order
            original_order = list(reversed(path))
            pattern_str = " ".join(original_order)
            patterns[pattern_str] = PatternInfo(
                pattern=pattern_str,
                tokens=tuple(original_order),
                phrase_ids=node.phrase_ids.copy(),
                tinyids=node.tinyids.copy(),
                frequency=node.count,
                k=len(path),
            )

        for token, child in node.children.items():
            traverse(child, path + [token])

    traverse(root, [])
    logger.debug(f"Suffix tree: {len(patterns)} patterns found")
    return patterns


def build_infix_index(
    phrases: List['PhraseRecord'],
    config: GrouperConfig
) -> Dict[str, PatternInfo]:
    """
    Build infix index using sliding window k-mers.

    For each phrase, extracts all k-mers (k_min to k_max) from
    all positions, building an inverted index of which phrases
    contain each k-mer.

    Args:
        phrases: List of PhraseRecord objects
        config: Grouper configuration

    Returns:
        Dict mapping pattern string to PatternInfo
    """
    # Inverted index: pattern -> set of phrase_ids
    kmer_index: Dict[str, Set[str]] = defaultdict(set)
    kmer_tinyids: Dict[str, Set[str]] = defaultdict(set)
    kmer_counts: Dict[str, int] = defaultdict(int)

    # Build inverted index
    for phrase in phrases:
        tokens = phrase.tokens
        seen_in_phrase = set()  # Track k-mers seen in this phrase

        for k in range(config.k_min, min(config.k_max + 1, len(tokens) + 1)):
            for start in range(len(tokens) - k + 1):
                kmer = tuple(tokens[start:start + k])
                kmer_str = " ".join(kmer)

                # Only count once per phrase for phrase membership
                if kmer_str not in seen_in_phrase:
                    kmer_index[kmer_str].add(phrase.phrase_id)
                    kmer_tinyids[kmer_str].update(phrase.tinyids)
                    seen_in_phrase.add(kmer_str)

                # Count total occurrences
                kmer_counts[kmer_str] += 1

    # Filter to patterns meeting criteria
    patterns = {}
    for pattern_str, phrase_ids in kmer_index.items():
        if len(phrase_ids) >= config.min_family_size:
            tokens = tuple(pattern_str.split())
            patterns[pattern_str] = PatternInfo(
                pattern=pattern_str,
                tokens=tokens,
                phrase_ids=phrase_ids.copy(),
                tinyids=kmer_tinyids[pattern_str].copy(),
                frequency=kmer_counts[pattern_str],
                k=len(tokens),
            )

    logger.debug(f"Infix index: {len(patterns)} patterns found")
    return patterns


def extract_families(
    patterns: Dict[str, PatternInfo],
    tree_type: str,
    config: GrouperConfig
) -> List[dict]:
    """
    Extract families from patterns, applying subsumption filtering.

    Longer patterns that contain all members of shorter patterns
    subsume them. We keep the maximal (longest) patterns.

    Args:
        patterns: Dict of pattern string to PatternInfo
        tree_type: "prefix", "suffix", or "infix"
        config: Grouper configuration

    Returns:
        List of family dicts with keys: family_id, pattern, member_count,
        total_tinyids, member_ids, examples
    """
    if not patterns:
        return []

    # Filter patterns by minimum content words (non-stopwords)
    filtered_patterns = [
        p for p in patterns.values()
        if count_content_words(p.tokens) >= config.min_content_words
    ]

    if not filtered_patterns:
        logger.debug(f"{tree_type}: All patterns filtered by min_content_words={config.min_content_words}")
        return []

    # Sort by k (length) descending, then by frequency descending
    sorted_patterns = sorted(
        filtered_patterns,
        key=lambda p: (-p.k, -p.frequency)
    )

    # Subsumption filtering: remove patterns whose members are
    # all contained in a longer pattern
    kept_patterns = []
    covered_phrase_ids: Set[str] = set()

    for pattern in sorted_patterns:
        # Check if this pattern adds new phrases
        new_phrases = pattern.phrase_ids - covered_phrase_ids

        # Keep pattern if it has enough unique members or is long enough
        # to be interesting
        if len(new_phrases) >= config.min_family_size:
            kept_patterns.append(pattern)
            covered_phrase_ids.update(pattern.phrase_ids)
        elif len(pattern.phrase_ids) >= config.min_family_size and pattern.k >= config.k_min + 2:
            # Also keep longer patterns even if subsumed, for completeness
            kept_patterns.append(pattern)

    # Build family records
    families = []
    for i, pattern in enumerate(kept_patterns):
        # Get example phrases (first 5)
        examples = list(pattern.phrase_ids)[:5]

        family = {
            "family_id": f"{tree_type}_{i:04d}",
            "pattern": pattern.pattern,
            "tokens": pattern.tokens,
            "member_count": len(pattern.phrase_ids),
            "total_tinyids": len(pattern.tinyids),
            "frequency": pattern.frequency,
            "k": pattern.k,
            "member_ids": list(pattern.phrase_ids),
            "examples": examples,
        }
        families.append(family)

    # Sort by member count descending
    families.sort(key=lambda f: -f["member_count"])

    return families


def assign_phrases_to_families(
    phrases: List['PhraseRecord'],
    all_families: Dict[str, List[dict]],
    config: GrouperConfig
) -> Dict[str, dict]:
    """
    Assign each phrase to its best-fit family based on strategy.

    Strategies:
    - frequency: Highest pattern frequency wins
    - longest: Longest matching pattern wins
    - all: Report all matches (assignment includes list)

    Args:
        phrases: List of PhraseRecord objects
        all_families: Dict mapping tree_type to list of families
        config: Grouper configuration

    Returns:
        Dict mapping phrase_id to assignment dict with keys:
        text, family_id, family_type, pattern, confidence, all_matches
    """
    # Build reverse index: phrase_id -> list of (family_type, family)
    phrase_to_families: Dict[str, List[Tuple[str, dict]]] = defaultdict(list)

    for family_type, families in all_families.items():
        for family in families:
            for phrase_id in family.get("member_ids", []):
                phrase_to_families[phrase_id].append((family_type, family))

    # Create assignments
    assignments = {}

    for phrase in phrases:
        matching_families = phrase_to_families.get(phrase.phrase_id, [])

        if not matching_families:
            # No family match
            assignments[phrase.phrase_id] = {
                "text": phrase.text,
                "family_id": "",
                "family_type": "",
                "pattern": "",
                "confidence": 0.0,
                "all_matches": [],
            }
            continue

        # Select best family based on strategy
        if config.assignment_strategy == "frequency":
            # Sort by frequency descending
            sorted_matches = sorted(
                matching_families,
                key=lambda x: -x[1].get("frequency", 0)
            )
        elif config.assignment_strategy == "longest":
            # Sort by pattern length (k) descending
            sorted_matches = sorted(
                matching_families,
                key=lambda x: -x[1].get("k", 0)
            )
        else:  # "all"
            sorted_matches = matching_families

        best_type, best_family = sorted_matches[0]

        # Calculate confidence based on how dominant this match is
        best_freq = best_family.get("frequency", 1)
        total_freq = sum(f.get("frequency", 1) for _, f in matching_families)
        confidence = best_freq / total_freq if total_freq > 0 else 0.0

        all_matches = [
            {"family_id": f["family_id"], "family_type": ft, "pattern": f["pattern"]}
            for ft, f in sorted_matches
        ]

        assignments[phrase.phrase_id] = {
            "text": phrase.text,
            "family_id": best_family["family_id"],
            "family_type": best_type,
            "pattern": best_family["pattern"],
            "confidence": confidence,
            "all_matches": all_matches,
        }

    return assignments
