"""
De Bruijn graph construction and contig extraction for k-mer extension.

This module implements de Bruijn graph-based phrase extension, which can
merge overlapping k-mers into longer contiguous sequences (contigs).

De Bruijn Graph Basics:
- Nodes represent (k-1)-mers (prefixes/suffixes of k-mers)
- Edges represent k-mers (connecting prefix to suffix)
- Contigs are maximal non-branching paths through the graph

This is useful for extending detected k-mer phrases when they share
overlapping substrings, potentially recovering longer meaningful phrases.

Example:
    k-mers: "patient reported", "reported outcome"
    De Bruijn extension: "patient reported outcome"
"""

from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class DBNode:
    """
    De Bruijn graph node representing a (k-1)-mer.

    Attributes:
        kmer_prefix: The (k-1) token sequence this node represents
        out_edges: Outgoing edges (next_token -> count)
        in_edges: Incoming edges (prev_token -> count)
    """
    kmer_prefix: Tuple[int, ...]
    out_edges: Dict[int, int] = field(default_factory=dict)  # next_token -> count
    in_edges: Dict[int, int] = field(default_factory=dict)   # prev_token -> count

    @property
    def out_degree(self) -> int:
        """Number of distinct outgoing edges"""
        return len(self.out_edges)

    @property
    def in_degree(self) -> int:
        """Number of distinct incoming edges"""
        return len(self.in_edges)

    def is_branch_point(self) -> bool:
        """True if this node is a branching point (in or out degree > 1)"""
        return self.out_degree > 1 or self.in_degree > 1

    def is_linear(self) -> bool:
        """True if exactly one in-edge and one out-edge"""
        return self.out_degree == 1 and self.in_degree == 1


class DeBruijnGraph:
    """
    De Bruijn graph for token sequences.

    Builds a graph where:
    - Nodes are (k-1)-mers (token prefixes/suffixes)
    - Edges are k-mers (full token sequences)

    Used to extend overlapping k-mers into longer phrases.
    """

    def __init__(self, k: int):
        """
        Initialize De Bruijn graph.

        Args:
            k: The k-mer size (nodes will be (k-1)-mers)
        """
        self.k = k
        self.nodes: Dict[Tuple[int, ...], DBNode] = {}
        self._built = False

    def add_kmer(self, kmer: Tuple[int, ...], count: int = 1):
        """
        Add a k-mer to the graph.

        Creates nodes for prefix and suffix (k-1)-mers and connects them.

        Args:
            kmer: Token sequence of length k
            count: Occurrence count for edge weighting
        """
        if len(kmer) != self.k:
            raise ValueError(f"Expected k-mer of length {self.k}, got {len(kmer)}")

        prefix = kmer[:-1]  # First (k-1) tokens
        suffix = kmer[1:]   # Last (k-1) tokens
        last_token = kmer[-1]
        first_token = kmer[0]

        # Create or get prefix node
        if prefix not in self.nodes:
            self.nodes[prefix] = DBNode(kmer_prefix=prefix)
        prefix_node = self.nodes[prefix]

        # Create or get suffix node
        if suffix not in self.nodes:
            self.nodes[suffix] = DBNode(kmer_prefix=suffix)
        suffix_node = self.nodes[suffix]

        # Add edges
        prefix_node.out_edges[last_token] = prefix_node.out_edges.get(last_token, 0) + count
        suffix_node.in_edges[first_token] = suffix_node.in_edges.get(first_token, 0) + count

        self._built = False

    def build(self):
        """Mark graph as built (for future optimizations)"""
        self._built = True

    def extract_contigs(self, min_length: int = 3, max_length: int = 50) -> List[List[int]]:
        """
        Extract maximal non-branching paths (contigs) from the graph.

        A contig is a path through the graph where all intermediate nodes
        have exactly one in-edge and one out-edge (linear path).

        Args:
            min_length: Minimum contig length in tokens
            max_length: Maximum contig length (prevents runaway paths)

        Returns:
            List of token sequences (contigs)
        """
        if not self.nodes:
            return []

        visited_edges: Set[Tuple[Tuple[int, ...], int]] = set()  # (node_prefix, out_token)
        contigs = []

        # Find start nodes: nodes that are branch points or have no in-edges
        # These are natural starting points for contigs
        start_nodes = []
        for prefix, node in self.nodes.items():
            # Start node conditions:
            # 1. No incoming edges (source)
            # 2. Branch point (multiple in/out)
            # 3. In-degree != out-degree (imbalanced)
            if node.in_degree == 0 or node.is_branch_point():
                start_nodes.append(prefix)

        # If no natural starts (all nodes linear), start from any node
        if not start_nodes and self.nodes:
            start_nodes = [next(iter(self.nodes.keys()))]

        # Extract contigs starting from each start node
        for start_prefix in start_nodes:
            start_node = self.nodes[start_prefix]

            for out_token in start_node.out_edges.keys():
                edge_key = (start_prefix, out_token)
                if edge_key in visited_edges:
                    continue

                # Start building contig
                contig = list(start_prefix) + [out_token]
                visited_edges.add(edge_key)

                # Follow linear path
                current_prefix = start_prefix[1:] + (out_token,)

                while len(contig) < max_length:
                    if current_prefix not in self.nodes:
                        break

                    current_node = self.nodes[current_prefix]

                    # Stop if branch point or no outgoing edges
                    if current_node.out_degree != 1:
                        break

                    # Get the single outgoing edge
                    next_token = next(iter(current_node.out_edges.keys()))
                    next_edge_key = (current_prefix, next_token)

                    if next_edge_key in visited_edges:
                        break

                    # Check if next node has multiple incoming edges
                    next_prefix = current_prefix[1:] + (next_token,)
                    if next_prefix in self.nodes:
                        next_node = self.nodes[next_prefix]
                        if next_node.in_degree > 1:
                            # Extend but don't continue past this branch point
                            contig.append(next_token)
                            visited_edges.add(next_edge_key)
                            break

                    # Extend contig
                    contig.append(next_token)
                    visited_edges.add(next_edge_key)
                    current_prefix = next_prefix

                # Save contig if long enough
                if len(contig) >= min_length:
                    contigs.append(contig)

        return contigs

    def get_statistics(self) -> Dict[str, int]:
        """Return graph statistics"""
        total_out_edges = sum(node.out_degree for node in self.nodes.values())
        branch_points = sum(1 for node in self.nodes.values() if node.is_branch_point())

        return {
            "num_nodes": len(self.nodes),
            "num_edges": total_out_edges,
            "branch_points": branch_points,
        }


def build_debruijn_graph(kmers: List[Tuple[int, ...]], k: int) -> DeBruijnGraph:
    """
    Build De Bruijn graph from k-mer list.

    Args:
        kmers: List of k-mer tuples (token ID sequences)
        k: K-mer length

    Returns:
        Populated DeBruijnGraph
    """
    graph = DeBruijnGraph(k)

    for kmer in kmers:
        graph.add_kmer(kmer)

    graph.build()
    return graph


def debruijn_extend_bin(kmer_counts, vocab, config) -> List:
    """
    Apply de Bruijn graph extension to k-mers in a frequency bin.

    This function attempts to merge overlapping k-mers into longer phrases
    using de Bruijn graph traversal.

    Args:
        kmer_counts: List of KmerCount objects from current k-bin
        vocab: Vocabulary for token-to-string conversion
        config: MinerConfig with extension parameters

    Returns:
        Extended k-mer counts (contigs as KmerCount objects)
        Falls back to original k-mers if no extensions found
    """
    from logic.phrase_miner import KmerCount

    if not kmer_counts:
        return []

    # Get k from first k-mer
    k = len(kmer_counts[0].kmer)

    # Build de Bruijn graph
    graph = DeBruijnGraph(k)
    kmer_to_count = {}  # Map kmer tuple to KmerCount

    for kc in kmer_counts:
        graph.add_kmer(kc.kmer, kc.frequency)
        kmer_to_count[kc.kmer] = kc

    graph.build()

    # Log graph statistics
    stats = graph.get_statistics()
    logger.debug(f"De Bruijn graph: {stats['num_nodes']} nodes, "
                 f"{stats['num_edges']} edges, {stats['branch_points']} branch points")

    # Extract contigs
    contigs = graph.extract_contigs(min_length=k, max_length=50)

    if not contigs:
        logger.debug("No contigs found, returning original k-mers")
        return kmer_counts

    # Convert contigs to KmerCount objects
    extended = []
    used_kmers = set()

    for contig in contigs:
        contig_tuple = tuple(contig)

        # Skip if this is just an original k-mer (no extension happened)
        if len(contig) == k and contig_tuple in kmer_to_count:
            continue

        # Merge metadata from constituent k-mers
        merged = merge_kmer_counts_for_contig(contig_tuple, kmer_counts, k)
        if merged:
            extended.append(merged)
            # Track which original k-mers were used
            for i in range(len(contig) - k + 1):
                subkmer = tuple(contig[i:i+k])
                used_kmers.add(subkmer)

    # Add back k-mers that weren't part of any contig
    for kc in kmer_counts:
        if kc.kmer not in used_kmers:
            extended.append(kc)

    logger.debug(f"De Bruijn extension: {len(kmer_counts)} k-mers -> "
                 f"{len(extended)} (extended: {len(contigs)}, kept: {len(extended) - len(contigs)})")

    return extended if extended else kmer_counts


def merge_kmer_counts_for_contig(contig_tuple: Tuple[int, ...],
                                  kmer_counts: List,
                                  k: int) -> Optional['KmerCount']:
    """
    Merge metadata from original k-mers that are contained in a contig.

    Creates a new KmerCount for the extended contig by combining:
    - tinyIds from all constituent k-mers
    - Occurrences from all constituent k-mers
    - Minimum frequency (conservative estimate)

    Args:
        contig_tuple: The extended token sequence
        kmer_counts: Original KmerCount objects
        k: Original k-mer length

    Returns:
        New KmerCount for contig, or None if no constituent k-mers found
    """
    from logic.phrase_miner import KmerCount

    merged_tinyids = set()
    merged_occurrences = []
    min_freq = float('inf')
    found_any = False

    # Build lookup for original k-mers
    kmer_lookup = {kc.kmer: kc for kc in kmer_counts}

    # Find all k-mers that are subsequences of this contig
    for i in range(len(contig_tuple) - k + 1):
        subkmer = contig_tuple[i:i+k]
        if subkmer in kmer_lookup:
            kc = kmer_lookup[subkmer]
            merged_tinyids.update(kc.tinyids)
            merged_occurrences.extend(kc.occurrences)
            min_freq = min(min_freq, kc.frequency)
            found_any = True

    if not found_any:
        return None

    return KmerCount(
        kmer=contig_tuple,
        frequency=int(min_freq) if min_freq != float('inf') else 0,
        tinyids=merged_tinyids,
        occurrences=merged_occurrences
    )


def is_subsequence(subseq: Tuple[int, ...], seq: Tuple[int, ...]) -> bool:
    """
    Check if subseq is a contiguous subsequence of seq.

    Args:
        subseq: Potential subsequence
        seq: Sequence to search in

    Returns:
        True if subseq appears contiguously in seq
    """
    n, m = len(seq), len(subseq)
    if m > n:
        return False
    for i in range(n - m + 1):
        if seq[i:i+m] == subseq:
            return True
    return False
