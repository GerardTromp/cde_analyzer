"""
Legacy Kmer-based Phrase Detection Algorithms

This module consolidates experimental kmer-based phrase detection algorithms
developed during the exploration phase of the project. These algorithms represent
different approaches to finding repeated phrases in CDE text fields.

Historical Context:
    Multiple iterations (v1-v4) of phrase building algorithms were developed to
    find optimal strategies for:
    - Building longest phrases from overlapping kmers
    - Extending phrases within and across frequency bins
    - Consolidating and merging overlapping phrases
    - Connecting phrases via common subphrases
    - Mapping lemmatized phrases back to verbatim text

Current Status:
    The production phrase detection system uses NLTK-based tokenization and
    lemmatization (utils/phrase_extraction.py) with recursive descent pattern
    matching (logic/phrase_extractor.py). Only kmer_extend_phrases1.py remains
    actively used in production.

Functions consolidated from:
    - kmer_build_longest_phrases[1-4].py: is_sub_kmer, build_longest_phrases
    - kmer_extend_phrases[2-3].py: extend_within_bins
    - kmer_consolidated_phrases[1-2].py: consolidate_phrases (both strategies)
    - kmer_connect_extendedphrase.py: group_connectors
    - kmer_enrich_w_verbatim.py: enrich_with_verbatim

Note:
    This is archival code. For production phrase detection, see:
    - utils/phrase_extraction.py (current implementation)
    - logic/phrase_extractor.py (current implementation)
    - utils/kmer_extend_phrases1.py (only active kmer code)
"""

from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple


# ==============================================================================
# SHARED UTILITIES
# ==============================================================================

def is_sub_kmer(small: tuple, large: tuple) -> bool:
    """
    Check if tuple `small` is a contiguous subsequence of tuple `large`.

    This utility function was duplicated across 5 original files.

    Args:
        small: Smaller kmer tuple to search for
        large: Larger kmer tuple to search within

    Returns:
        True if small is found as contiguous subsequence in large

    Example:
        >>> is_sub_kmer(('a', 'b'), ('x', 'a', 'b', 'c'))
        True
        >>> is_sub_kmer(('a', 'c'), ('x', 'a', 'b', 'c'))
        False
    """
    n, m = len(small), len(large)
    for i in range(m - n + 1):
        if large[i:i+n] == small:
            return True
    return False


# ==============================================================================
# PHRASE BUILDING ALGORITHMS
# ==============================================================================

def build_longest_phrases_simple(kmer_table: List[Dict]) -> List[Dict]:
    """
    Build longest phrases from kmers (Version 1 - Simple).

    Original file: kmer_build_longest_phrases.py, kmer_phrase_detection.py

    Algorithm:
        1. Group kmers by count (frequency)
        2. Process highest-count bins first
        3. For each kmer, extend forward by matching overlapping kmers
        4. Mark all sub-kmers as discarded to avoid redundancy

    Args:
        kmer_table: List of dicts with keys: kmer (tuple), k (int), count (int)

    Returns:
        List of dicts with keys: phrase (tuple), k (int), count (int)
    """
    count_bins = defaultdict(list)
    for row in kmer_table:
        count_bins[row["count"]].append(row)

    results = []
    discarded = set()

    for count in sorted(count_bins.keys(), reverse=True):
        kmers = sorted(count_bins[count], key=lambda r: -r["k"])
        used = set()

        for row in kmers:
            kmer = row["kmer"]
            if kmer in discarded or kmer in used:
                continue

            phrase = list(kmer)
            used.add(kmer)

            # Extend forward as long as possible
            extended = True
            while extended:
                extended = False
                for nxt in kmers:
                    if nxt["kmer"] in discarded or nxt["kmer"] in used:
                        continue
                    # If last k-1 words of phrase match prefix of candidate
                    if tuple(phrase[-(nxt["k"]-1):]) == nxt["kmer"][:-1]:
                        phrase.append(nxt["kmer"][-1])
                        used.add(nxt["kmer"])
                        extended = True
                        break

            phrase_tuple = tuple(phrase)
            results.append({
                "phrase": phrase_tuple,
                "k": len(phrase_tuple),
                "count": count
            })

            # Mark all sub-kmers inside this phrase as discarded
            for row2 in kmers:
                if row2["kmer"] not in discarded and is_sub_kmer(row2["kmer"], phrase_tuple):
                    discarded.add(row2["kmer"])

    return results


def build_longest_phrases_with_tracking(kmer_table: List[Dict]) -> List[Dict]:
    """
    Build longest phrases with tinyId and field tracking (Version 2/3).

    Original files: kmer_build_longest_phrases2.py (kmer_source),
                    kmer_build_longest_phrases3.py (tinyId)

    Enhanced version that tracks which tinyIds contributed to each phrase
    and which fields the phrase appears in.

    Args:
        kmer_table: List of dicts with keys:
            - kmer: list[str] or tuple[str]
            - k: int
            - count: int
            - kmer_source or tinyId: list[str] (tinyIds)
            - field: str (optional)

    Returns:
        List of dicts with keys:
            - phrase: list[str] (JSON-safe)
            - k: int
            - count: int
            - kmer_source: list[str] (sorted tinyIds)
            - fields: list[str] (sorted field names)
    """
    # Normalize kmers to tuples
    for row in kmer_table:
        if not isinstance(row["kmer"], tuple):
            row["kmer"] = tuple(row["kmer"])

    count_bins = defaultdict(list)
    for row in kmer_table:
        count_bins[row["count"]].append(row)

    results = []
    discarded = set()

    for count in sorted(count_bins.keys(), reverse=True):
        kmers = sorted(count_bins[count], key=lambda r: -r["k"])
        used = set()

        for row in kmers:
            kmer = row["kmer"]
            if kmer in discarded or kmer in used:
                continue

            phrase = list(kmer)
            # Support both kmer_source and tinyId keys
            merged_sources = set(row.get("kmer_source") or row.get("tinyId") or [])
            fields = set([row.get("field")]) if row.get("field") else set()

            used.add(kmer)
            extended = True

            while extended:
                extended = False
                for nxt in kmers:
                    nkmer = nxt["kmer"]
                    if nkmer in discarded or nkmer in used:
                        continue
                    if tuple(phrase[-(nxt["k"]-1):]) == nkmer[:-1]:
                        phrase.append(nkmer[-1])
                        merged_sources.update(nxt.get("kmer_source") or nxt.get("tinyId") or [])
                        if nxt.get("field"):
                            fields.add(nxt["field"])
                        used.add(nkmer)
                        extended = True
                        break

            phrase_tuple = tuple(phrase)
            results.append({
                "phrase": list(phrase_tuple),
                "k": len(phrase_tuple),
                "count": count,
                "kmer_source": sorted(merged_sources),
                "fields": sorted(fields)
            })

            # Discard subsumed kmers
            for row2 in kmers:
                if row2["kmer"] not in discarded and is_sub_kmer(row2["kmer"], phrase_tuple):
                    discarded.add(row2["kmer"])

    return results


def build_longest_phrases_iterative(kmer_table: List[Dict]) -> List[Dict]:
    """
    Build longest phrases with iterative bin processing (Version 4 - Best).

    Original file: kmer_build_longest_phrases4.py

    This version processes one count bin at a time, removing consumed kmers
    before processing the next bin. This allows for cleaner separation of
    phrase frequencies.

    Args:
        kmer_table: List of dicts with keys:
            - kmer: list[str] or tuple[str]
            - k: int
            - count: int
            - kmer_source: list[str] (optional)
            - field: str (optional)

    Returns:
        List of phrase dicts accumulated from all bins
    """
    def extend_phrases_once(working_table: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Process highest-count bin, return phrases and remaining kmers."""
        if not working_table:
            return [], []

        # Normalize kmers to tuples
        for row in working_table:
            if not isinstance(row["kmer"], tuple):
                row["kmer"] = tuple(row["kmer"])

        # Group by count
        count_bins = defaultdict(list)
        for row in working_table:
            count_bins[row["count"]].append(row)

        # Take highest count bin
        top_count = max(count_bins.keys())
        kmers = sorted(count_bins[top_count], key=lambda r: -r["k"])

        results = []
        consumed = set()
        used = set()

        for row in kmers:
            kmer = row["kmer"]
            if kmer in consumed or kmer in used:
                continue

            phrase = list(kmer)
            merged_sources = set(row.get("kmer_source", []))
            fields = set([row.get("field")]) if row.get("field") else set()

            used.add(kmer)
            extended = True
            while extended:
                extended = False
                for nxt in kmers:
                    nkmer = nxt["kmer"]
                    if nkmer in consumed or nkmer in used:
                        continue
                    if tuple(phrase[-(nxt["k"]-1):]) == nkmer[:-1]:
                        phrase.append(nkmer[-1])
                        merged_sources.update(nxt.get("kmer_source", []))
                        if nxt.get("field"):
                            fields.add(nxt["field"])
                        used.add(nkmer)
                        extended = True
                        break

            phrase_tuple = tuple(phrase)
            results.append({
                "phrase": list(phrase_tuple),
                "k": len(phrase_tuple),
                "count": top_count,
                "kmer_source": sorted(merged_sources),
                "fields": sorted(fields)
            })

            # Mark all sub-kmers as consumed
            for row2 in kmers:
                if row2["kmer"] not in consumed and is_sub_kmer(row2["kmer"], phrase_tuple):
                    consumed.add(row2["kmer"])

        # Remove consumed kmers from dataset
        remaining = [row for row in working_table if row["kmer"] not in consumed]

        return results, remaining

    # Iteratively process all bins
    all_results = []
    working = kmer_table[:]
    while working:
        results, working = extend_phrases_once(working)
        all_results.extend(results)
    return all_results


# ==============================================================================
# PHRASE EXTENSION ALGORITHMS
# ==============================================================================

def extend_within_bins_basic(phrases: List[Dict]) -> List[Dict]:
    """
    Extend phrases within same (count, k) bin (Version 2).

    Original file: kmer_extend_phrases2.py

    Uses prefix/suffix indexing for efficient bidirectional extension.

    Args:
        phrases: List of dicts with keys: phrase, k, count, tinyIds

    Returns:
        Extended phrases with merged tinyIds
    """
    bins = defaultdict(list)
    for ph in phrases:
        bins[(ph["count"], ph["k"])].append(ph)

    extended_phrases = []

    for (count, k), bin_phrases in bins.items():
        # Build index by prefix and suffix
        prefix_index = defaultdict(list)
        suffix_index = defaultdict(list)

        for ph in bin_phrases:
            prefix_index[tuple(ph["phrase"][:-1])].append(ph)
            suffix_index[tuple(ph["phrase"][1:])].append(ph)

        visited = set()

        for ph in bin_phrases:
            if id(ph) in visited:
                continue

            current = ph
            phrase_words = current["phrase"][:]
            tinyIds = set(current["tinyIds"])
            visited.add(id(current))

            # Extend forward
            while tuple(phrase_words[1:]) in prefix_index:
                candidates = prefix_index[tuple(phrase_words[1:])]
                next_ph = None
                for cand in candidates:
                    if id(cand) not in visited:
                        next_ph = cand
                        break
                if not next_ph:
                    break
                phrase_words.append(next_ph["phrase"][-1])
                tinyIds.update(next_ph["tinyIds"])
                visited.add(id(next_ph))

            # Extend backward
            while tuple(phrase_words[:-1]) in suffix_index:
                candidates = suffix_index[tuple(phrase_words[:-1])]
                prev_ph = None
                for cand in candidates:
                    if id(cand) not in visited:
                        prev_ph = cand
                        break
                if not prev_ph:
                    break
                phrase_words.insert(0, prev_ph["phrase"][0])
                tinyIds.update(prev_ph["tinyIds"])
                visited.add(id(prev_ph))

            extended_phrases.append({
                "phrase": phrase_words,
                "k": len(phrase_words),
                "count": count,
                "tinyIds": sorted(tinyIds),
                "bin": (count, k)
            })

    return extended_phrases


def extend_within_bins_with_dedup(phrases: List[Dict]) -> List[Dict]:
    """
    Extend phrases within bins with deduplication (Version 3 - Best).

    Original file: kmer_extend_phrases3.py

    Same as basic version but removes contained phrases within each bin
    after extension to reduce redundancy.

    Args:
        phrases: List of dicts with keys: phrase, k, count, tinyIds

    Returns:
        Extended and deduplicated phrases
    """
    bins = defaultdict(list)
    for ph in phrases:
        bins[(ph["count"], ph["k"])].append(ph)

    extended_phrases = []

    for (count, k), bin_phrases in bins.items():
        # Build index by prefix and suffix
        prefix_index = defaultdict(list)
        suffix_index = defaultdict(list)

        for ph in bin_phrases:
            prefix_index[tuple(ph["phrase"][:-1])].append(ph)
            suffix_index[tuple(ph["phrase"][1:])].append(ph)

        visited = set()
        bin_extended = []

        for ph in bin_phrases:
            if id(ph) in visited:
                continue

            current = ph
            phrase_words = current["phrase"][:]
            tinyIds = set(current["tinyIds"])
            visited.add(id(current))

            # Extend forward
            while tuple(phrase_words[1:]) in prefix_index:
                candidates = prefix_index[tuple(phrase_words[1:])]
                next_ph = None
                for cand in candidates:
                    if id(cand) not in visited:
                        next_ph = cand
                        break
                if not next_ph:
                    break
                phrase_words.append(next_ph["phrase"][-1])
                tinyIds.update(next_ph["tinyIds"])
                visited.add(id(next_ph))

            # Extend backward
            while tuple(phrase_words[:-1]) in suffix_index:
                candidates = suffix_index[tuple(phrase_words[:-1])]
                prev_ph = None
                for cand in candidates:
                    if id(cand) not in visited:
                        prev_ph = cand
                        break
                if not prev_ph:
                    break
                phrase_words.insert(0, prev_ph["phrase"][0])
                tinyIds.update(prev_ph["tinyIds"])
                visited.add(id(prev_ph))

            bin_extended.append({
                "phrase": phrase_words,
                "k": len(phrase_words),
                "count": count,
                "tinyIds": sorted(tinyIds),
                "bin": (count, k)
            })

        # Deduplicate inside this bin
        deduped = []
        bin_extended.sort(key=lambda x: (-len(x["phrase"]), x["phrase"]))
        seen = set()
        for ph in bin_extended:
            ph_tuple = tuple(ph["phrase"])
            # Check if contained in any longer phrase already kept
            if any(
                ph_tuple in tuple(other["phrase"][j:j+len(ph_tuple)])
                for other in deduped
                for j in range(len(other["phrase"]) - len(ph_tuple) + 1)
            ):
                continue
            if ph_tuple not in seen:
                seen.add(ph_tuple)
                deduped.append(ph)

        extended_phrases.extend(deduped)

    return extended_phrases


# ==============================================================================
# PHRASE CONSOLIDATION ALGORITHMS
# ==============================================================================

def consolidate_phrases_by_merging(phrases: List[Dict]) -> List[Dict]:
    """
    Consolidate phrases by merging overlapping ones (Strategy 1).

    Original file: kmer_consolidated_phrases1.py

    Iteratively merges phrases with suffix/prefix overlap until no more
    merges are possible.

    Args:
        phrases: List of phrase dicts (all same count)

    Returns:
        Merged phrases with combined kmer_source and fields
    """
    changed = True
    while changed:
        changed = False
        new_phrases = []
        used = [False] * len(phrases)

        for i, p1 in enumerate(phrases):
            if used[i]:
                continue
            merged = False
            for j, p2 in enumerate(phrases):
                if i == j or used[j]:
                    continue
                a, b = p1["phrase"], p2["phrase"]

                # Check for suffix/prefix overlap
                for overlap in range(min(len(a), len(b)) - 1, 0, -1):
                    if a[-overlap:] == b[:overlap]:
                        merged_phrase = a + b[overlap:]
                        new_phrases.append({
                            "phrase": merged_phrase,
                            "k": len(merged_phrase),
                            "count": p1["count"],
                            "kmer_source": sorted(set(p1["kmer_source"]) | set(p2["kmer_source"])),
                            "fields": sorted(set(p1["fields"]) | set(p2["fields"]))
                        })
                        used[i] = used[j] = True
                        merged = True
                        changed = True
                        break

                if merged:
                    break

            if not merged:
                new_phrases.append(p1)
                used[i] = True

        phrases = new_phrases

    return phrases


def consolidate_phrases_by_pruning(phrases: List[Dict]) -> List[Dict]:
    """
    Consolidate phrases by removing subsequences (Strategy 2).

    Original file: kmer_consolidated_phrases2.py

    Within each count bin, keeps only the longest phrases and removes
    any phrase that is a contiguous subsequence of a longer one.

    Args:
        phrases: List of phrase dicts with keys: phrase, count, k, etc.

    Returns:
        Pruned list with redundant subsequences removed
    """
    def is_subsequence(short: List[str], long: List[str]) -> bool:
        """Check if short is contiguous subsequence of long."""
        if len(short) > len(long):
            return False
        for i in range(len(long) - len(short) + 1):
            if long[i:i+len(short)] == short:
                return True
        return False

    # Group by count
    bins: Dict[int, List[Dict]] = {}
    for p in phrases:
        bins.setdefault(p["count"], []).append(p)

    consolidated = []
    for count, group in bins.items():
        # Sort by length descending
        group_sorted = sorted(group, key=lambda x: len(x["phrase"]), reverse=True)
        kept = []
        for cand in group_sorted:
            # Check if already covered by a longer kept phrase
            if any(is_subsequence(cand["phrase"], longer["phrase"]) for longer in kept):
                continue
            kept.append(cand)
        consolidated.extend(kept)

    return consolidated


# ==============================================================================
# ADVANCED PHRASE ANALYSIS
# ==============================================================================

def group_connectors(
    phrases: List[Dict],
    min_branch: int = 2,
    constrain_fields: bool = False,
    both_directions: bool = True,
) -> List[Dict]:
    """
    Group phrases around common connector phrases (Phase 3 processing).

    Original file: kmer_connect_extendedphrase.py

    Identifies connector phrases that appear as prefixes or suffixes of
    multiple extended phrases. Groups branches around these connectors
    and recomputes counts based on the union of tinyIds.

    Args:
        phrases: Output from phrase extension/polishing
        min_branch: Minimum divergent extensions to qualify as connector
        constrain_fields: Only merge branches with same field(s)
        both_directions: Consider both prefix and suffix connectors

    Returns:
        List of connector group dicts with:
            - connector: dict with phrase and recomputed counts
            - branches: list of branch phrase dicts
            - direction: "prefix" or "suffix"
    """
    phrase_map = {tuple(p["phrase"]): p for p in phrases}
    connector_groups = []
    used = set()

    def process_connector(conn_phrase: tuple, branches: List[Dict], direction: str) -> Optional[List[Dict]]:
        """Build connector group, recomputing counts."""
        if len(branches) < min_branch:
            return None

        # Field partitioning
        if constrain_fields:
            groups = defaultdict(list)
            for b in branches:
                for f in b["fields"]:
                    groups[f].append(b)
        else:
            groups = {"*": branches}

        results = []
        for field, branch_list in groups.items():
            if len(branch_list) < min_branch:
                continue

            connector = phrase_map[conn_phrase]

            branch_ids = set().union(*(b["tinyIds"] for b in branch_list))
            branch_fields = set().union(*(b["fields"] for b in branch_list))

            connector_recomputed = {
                "phrase": list(conn_phrase),
                "count": len(branch_ids),
                "tinyIds": branch_ids,
                "fields": branch_fields,
                "original_count": connector["count"],
            }

            group = {
                "connector": connector_recomputed,
                "branches": branch_list,
                "direction": direction,
            }
            results.append(group)

            used.add(conn_phrase)
            for b in branch_list:
                used.add(tuple(b["phrase"]))

        return results

    # Find prefix connectors
    prefix_groups = defaultdict(list)
    for ph in phrases:
        for i in range(1, len(ph["phrase"])):
            prefix = tuple(ph["phrase"][:i])
            if prefix in phrase_map:
                prefix_groups[prefix].append(tuple(ph["phrase"]))

    for prefix, exts in prefix_groups.items():
        branches = [phrase_map[e] for e in exts if e in phrase_map]
        results = process_connector(prefix, branches, "prefix")
        if results:
            connector_groups.extend(results)

    # Find suffix connectors
    if both_directions:
        suffix_groups = defaultdict(list)
        for ph in phrases:
            for i in range(1, len(ph["phrase"])):
                suffix = tuple(ph["phrase"][i:])
                if suffix in phrase_map:
                    suffix_groups[suffix].append(tuple(ph["phrase"]))

        for suffix, exts in suffix_groups.items():
            branches = [phrase_map[e] for e in exts if e in phrase_map]
            results = process_connector(suffix, branches, "suffix")
            if results:
                connector_groups.extend(results)

    return connector_groups


def enrich_with_verbatim(
    phrases: List[Dict[str, Any]],
    tinyid_to_verbatim: Dict[str, str],
    add_variant_count: bool = True
) -> List[Dict[str, Any]]:
    """
    Map lemmatized phrases back to verbatim text variants.

    Original file: kmer_enrich_w_verbatim.py

    Uses tinyId mapping to recover the original verbatim wording for each
    lemmatized phrase, allowing analysis of surface form variations.

    Args:
        phrases: List of phrase dicts from polishing/connector phase
        tinyid_to_verbatim: Mapping of tinyId -> original verbatim text
        add_variant_count: Include count of each verbatim variant

    Returns:
        Enriched phrases with 'verbatim_variants' attached:
        [
          {
            "phrase": [...],           # lemma tokens
            "k": ...,
            "count": ...,
            "tinyIds": [...],
            "fields": [...],
            "verbatim_variants": [
                {"text": "...", "tinyIds": [...], "count": N},
                ...
            ]
          }
        ]
    """
    enriched = []

    for record in phrases:
        variant_map = defaultdict(list)

        for tid in record.get("tinyIds", []):
            if tid in tinyid_to_verbatim:
                text = tinyid_to_verbatim[tid]
                variant_map[text].append(tid)

        verbatim_variants = []
        for text, tids in variant_map.items():
            variant_info = {"text": text, "tinyIds": tids}
            if add_variant_count:
                variant_info["count"] = len(tids)
            verbatim_variants.append(variant_info)

        enriched.append({
            **record,
            "verbatim_variants": verbatim_variants
        })

    return enriched
