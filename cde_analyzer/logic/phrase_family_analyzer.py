"""
Phrase Family Analyzer - Detect phrase families using prefix/suffix analysis.

Analyzes non-instrument phrases to discover "families" based on:
- Common prefixes: "patient reported outcome", "patient health questionnaire"
- Common suffixes: "questionnaire", "scale", "inventory"
- Shared stems/roots

Uses trie-based data structures for efficient prefix/suffix matching.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TrieNode:
    """Node in a prefix/suffix trie."""
    children: Dict[str, 'TrieNode'] = field(default_factory=dict)
    is_terminal: bool = False
    phrase_ids: Set[str] = field(default_factory=set)
    count: int = 0


@dataclass
class PhraseFamily:
    """A family of related phrases sharing a common pattern."""
    family_id: str
    family_type: str  # "prefix", "suffix", or "stem"
    pattern: str  # The common pattern (e.g., "patient reported", "questionnaire")
    pattern_display: str  # Display form with wildcard (e.g., "patient reported *")
    members: List[str]  # List of phrase lemmas in this family
    member_count: int
    total_frequency: int
    distinct_tinyids: int


class PrefixTrie:
    """Trie for finding common prefixes in phrases."""

    def __init__(self, min_prefix_words: int = 2):
        self.root = TrieNode()
        self.min_prefix_words = min_prefix_words
        self.phrase_data: Dict[str, Tuple[int, int]] = {}  # phrase_id -> (freq, n_tinyids)

    def insert(self, phrase_id: str, lemma_text: str, frequency: int, n_tinyids: int):
        """Insert a phrase into the trie."""
        words = lemma_text.split()
        if len(words) < self.min_prefix_words:
            return

        self.phrase_data[phrase_id] = (frequency, n_tinyids)
        node = self.root
        for word in words:
            if word not in node.children:
                node.children[word] = TrieNode()
            node = node.children[word]
            node.count += 1
            node.phrase_ids.add(phrase_id)
        node.is_terminal = True

    def find_common_prefixes(self, min_count: int = 3) -> List[Tuple[str, Set[str], int]]:
        """
        Find common prefixes shared by multiple phrases.

        Args:
            min_count: Minimum number of phrases to qualify as a common prefix.

        Returns:
            List of (prefix_text, phrase_ids, count) tuples.
        """
        results = []
        self._find_prefixes_recursive(
            self.root, [], min_count, self.min_prefix_words, results
        )
        # Sort by count descending
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def _find_prefixes_recursive(
        self,
        node: TrieNode,
        path: List[str],
        min_count: int,
        min_words: int,
        results: List[Tuple[str, Set[str], int]]
    ):
        """Recursively find common prefixes."""
        # Check if this path qualifies as a common prefix
        if len(path) >= min_words and node.count >= min_count:
            # Only add if there's branching (multiple different continuations)
            # or this is a natural prefix boundary
            n_children = len(node.children)
            if n_children >= 2 or (n_children == 0 and node.is_terminal):
                # Add this prefix
                prefix_text = ' '.join(path)
                results.append((prefix_text, node.phrase_ids.copy(), node.count))

        # Recurse into children
        for word, child in node.children.items():
            self._find_prefixes_recursive(
                child, path + [word], min_count, min_words, results
            )


class SuffixTrie:
    """Trie for finding common suffixes in phrases (built from reversed words)."""

    def __init__(self, min_suffix_words: int = 1):
        self.root = TrieNode()
        self.min_suffix_words = min_suffix_words
        self.phrase_data: Dict[str, Tuple[int, int]] = {}

    def insert(self, phrase_id: str, lemma_text: str, frequency: int, n_tinyids: int):
        """Insert a phrase into the suffix trie (words reversed)."""
        words = lemma_text.split()
        if len(words) < self.min_suffix_words:
            return

        self.phrase_data[phrase_id] = (frequency, n_tinyids)
        node = self.root
        # Insert words in reverse order for suffix matching
        for word in reversed(words):
            if word not in node.children:
                node.children[word] = TrieNode()
            node = node.children[word]
            node.count += 1
            node.phrase_ids.add(phrase_id)
        node.is_terminal = True

    def find_common_suffixes(self, min_count: int = 3) -> List[Tuple[str, Set[str], int]]:
        """
        Find common suffixes shared by multiple phrases.

        Args:
            min_count: Minimum number of phrases to qualify as a common suffix.

        Returns:
            List of (suffix_text, phrase_ids, count) tuples.
        """
        results = []
        self._find_suffixes_recursive(
            self.root, [], min_count, self.min_suffix_words, results
        )
        # Sort by count descending
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def _find_suffixes_recursive(
        self,
        node: TrieNode,
        path: List[str],
        min_count: int,
        min_words: int,
        results: List[Tuple[str, Set[str], int]]
    ):
        """Recursively find common suffixes."""
        if len(path) >= min_words and node.count >= min_count:
            n_children = len(node.children)
            if n_children >= 2 or (n_children == 0 and node.is_terminal):
                # Reverse path back to get correct suffix order
                suffix_text = ' '.join(reversed(path))
                results.append((suffix_text, node.phrase_ids.copy(), node.count))

        for word, child in node.children.items():
            self._find_suffixes_recursive(
                child, path + [word], min_count, min_words, results
            )


@dataclass
class FamilyAnalysisConfig:
    """Configuration for phrase family analysis."""
    min_prefix_words: int = 2      # Minimum words for prefix pattern
    min_suffix_words: int = 1      # Minimum words for suffix pattern
    min_family_size: int = 3       # Minimum members to form a family
    max_families: int = 100        # Maximum families to report
    include_prefixes: bool = True  # Analyze prefix patterns
    include_suffixes: bool = True  # Analyze suffix patterns


class PhraseFamilyAnalyzer:
    """Analyzes phrases to discover family groupings."""

    def __init__(self, config: Optional[FamilyAnalysisConfig] = None):
        self.config = config or FamilyAnalysisConfig()
        self.prefix_trie = PrefixTrie(min_prefix_words=self.config.min_prefix_words)
        self.suffix_trie = SuffixTrie(min_suffix_words=self.config.min_suffix_words)
        self.phrase_lemmas: Dict[str, str] = {}  # phrase_id -> lemma_text
        self.phrase_data: Dict[str, Tuple[int, int]] = {}  # phrase_id -> (freq, n_tinyids)

    def load_phrases_from_tsv(self, filepath: str):
        """
        Load phrases from verbatim_phrases.tsv or similar.

        Expected columns: phrase_id, lemma_text, verbatim_text, verbatim_count, tinyids
        """
        logger.info(f"Loading phrases from {filepath}")
        count = 0

        with open(filepath, encoding="utf-8") as f:
            header = f.readline().strip()
            headers = header.split('\t')

            # Find column indices
            try:
                id_idx = headers.index("phrase_id")
                lemma_idx = headers.index("lemma_text")
                count_idx = headers.index("verbatim_count")
                tinyids_idx = headers.index("tinyids")
            except ValueError as e:
                logger.error(f"Missing required column: {e}")
                raise

            for line in f:
                line = line.strip()
                if not line:
                    continue

                fields = line.split('\t')
                if len(fields) <= max(id_idx, lemma_idx, count_idx, tinyids_idx):
                    continue

                phrase_id = fields[id_idx]
                lemma_text = fields[lemma_idx]
                try:
                    frequency = int(fields[count_idx])
                except ValueError:
                    frequency = 1

                tinyids_str = fields[tinyids_idx]
                # Support both space-separated and pipe-separated formats (or mixed)
                n_tinyids = len([t for t in re.split(r'[\s|]+', tinyids_str) if t]) if tinyids_str else 0

                self.phrase_lemmas[phrase_id] = lemma_text
                self.phrase_data[phrase_id] = (frequency, n_tinyids)

                # Insert into tries
                if self.config.include_prefixes:
                    self.prefix_trie.insert(phrase_id, lemma_text, frequency, n_tinyids)
                if self.config.include_suffixes:
                    self.suffix_trie.insert(phrase_id, lemma_text, frequency, n_tinyids)

                count += 1

        logger.info(f"Loaded {count} phrases for family analysis")

    def analyze(self) -> List[PhraseFamily]:
        """
        Perform family analysis and return discovered families.

        Returns:
            List of PhraseFamily objects, sorted by member count.
        """
        families = []
        family_id_counter = 0

        # Find prefix families
        if self.config.include_prefixes:
            prefix_patterns = self.prefix_trie.find_common_prefixes(
                min_count=self.config.min_family_size
            )
            logger.info(f"Found {len(prefix_patterns)} prefix patterns")

            for pattern, phrase_ids, count in prefix_patterns[:self.config.max_families // 2]:
                family_id_counter += 1
                members = [self.phrase_lemmas[pid] for pid in phrase_ids if pid in self.phrase_lemmas]
                total_freq = sum(self.phrase_data.get(pid, (0, 0))[0] for pid in phrase_ids)
                distinct_tinyids = sum(self.phrase_data.get(pid, (0, 0))[1] for pid in phrase_ids)

                family = PhraseFamily(
                    family_id=f"prefix_{family_id_counter:04d}",
                    family_type="prefix",
                    pattern=pattern,
                    pattern_display=f"{pattern} *",
                    members=sorted(members),
                    member_count=len(members),
                    total_frequency=total_freq,
                    distinct_tinyids=distinct_tinyids
                )
                families.append(family)

        # Find suffix families
        if self.config.include_suffixes:
            suffix_patterns = self.suffix_trie.find_common_suffixes(
                min_count=self.config.min_family_size
            )
            logger.info(f"Found {len(suffix_patterns)} suffix patterns")

            for pattern, phrase_ids, count in suffix_patterns[:self.config.max_families // 2]:
                family_id_counter += 1
                members = [self.phrase_lemmas[pid] for pid in phrase_ids if pid in self.phrase_lemmas]
                total_freq = sum(self.phrase_data.get(pid, (0, 0))[0] for pid in phrase_ids)
                distinct_tinyids = sum(self.phrase_data.get(pid, (0, 0))[1] for pid in phrase_ids)

                family = PhraseFamily(
                    family_id=f"suffix_{family_id_counter:04d}",
                    family_type="suffix",
                    pattern=pattern,
                    pattern_display=f"* {pattern}",
                    members=sorted(members),
                    member_count=len(members),
                    total_frequency=total_freq,
                    distinct_tinyids=distinct_tinyids
                )
                families.append(family)

        # Sort by member count descending
        families.sort(key=lambda f: f.member_count, reverse=True)

        # Limit to max_families
        return families[:self.config.max_families]

    def write_families_tsv(self, filepath: str, families: List[PhraseFamily]):
        """Write phrase families to TSV file."""
        logger.info(f"Writing {len(families)} families to {filepath}")

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            # Header
            f.write("family_id\tfamily_type\tpattern\tpattern_display\t"
                    "member_count\ttotal_frequency\tdistinct_tinyids\ttop_members\n")

            for family in families:
                # Show top 5 members
                top_members = family.members[:5]
                top_members_str = " | ".join(top_members)
                if len(family.members) > 5:
                    top_members_str += f" | ... (+{len(family.members) - 5} more)"

                f.write(f"{family.family_id}\t{family.family_type}\t{family.pattern}\t"
                        f"{family.pattern_display}\t{family.member_count}\t"
                        f"{family.total_frequency}\t{family.distinct_tinyids}\t"
                        f"{top_members_str}\n")

    def write_family_members_tsv(self, filepath: str, families: List[PhraseFamily]):
        """Write detailed family membership to TSV file."""
        logger.info(f"Writing family membership details to {filepath}")

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            # Header
            f.write("family_id\tfamily_type\tpattern\tmember_lemma\n")

            for family in families:
                for member in family.members:
                    f.write(f"{family.family_id}\t{family.family_type}\t"
                            f"{family.pattern}\t{member}\n")


def analyze_phrase_families(
    input_tsv: str,
    output_dir: str,
    config: Optional[FamilyAnalysisConfig] = None
) -> List[PhraseFamily]:
    """
    Main entry point for phrase family analysis.

    Args:
        input_tsv: Path to verbatim_phrases.tsv
        output_dir: Directory to write output files
        config: Optional analysis configuration

    Returns:
        List of discovered phrase families
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    analyzer = PhraseFamilyAnalyzer(config)
    analyzer.load_phrases_from_tsv(input_tsv)

    families = analyzer.analyze()

    # Write outputs
    analyzer.write_families_tsv(str(output_path / "phrase_families.tsv"), families)
    analyzer.write_family_members_tsv(str(output_path / "phrase_family_members.tsv"), families)

    logger.info(f"Analysis complete: {len(families)} families discovered")
    return families
