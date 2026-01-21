"""
Verbatim text coalescing for overlapping phrase fragments.

When phrase mining extracts verbatim text using sliding token windows,
multiple overlapping fragments may be extracted from the same source text.
This module provides functions to coalesce these fragments into a single
merged string representing the full extent of the source text.

Example:
    Input fragments (all from same tinyId set):
        "harmful and usually subject to legal restriction), or over-the-counter"
        "and usually subject to legal restriction), or over-the-counter drugs"
        "usually subject to legal restriction), or over-the-counter drugs (medicine"

    Output (coalesced):
        "harmful and usually subject to legal restriction), or over-the-counter drugs (medicine"
"""

from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict


def find_overlap(s1: str, s2: str, min_overlap: int = 10) -> Optional[int]:
    """
    Find overlap where suffix of s1 matches prefix of s2.

    Args:
        s1: First string (check its suffix)
        s2: Second string (check its prefix)
        min_overlap: Minimum overlap length to consider valid

    Returns:
        Length of overlap if found, None otherwise
    """
    max_overlap = min(len(s1), len(s2))
    for overlap_len in range(max_overlap, min_overlap - 1, -1):
        if s1[-overlap_len:] == s2[:overlap_len]:
            return overlap_len
    return None


def merge_two_strings(s1: str, s2: str, min_overlap: int = 10) -> Optional[str]:
    """
    Merge two overlapping strings if they share a common overlap region.

    Tries both orderings (s1+s2 and s2+s1) and returns the merge if found.

    Args:
        s1: First string
        s2: Second string
        min_overlap: Minimum overlap length required

    Returns:
        Merged string if overlap found, None otherwise
    """
    # Try s1 followed by s2
    overlap = find_overlap(s1, s2, min_overlap)
    if overlap:
        return s1 + s2[overlap:]

    # Try s2 followed by s1
    overlap = find_overlap(s2, s1, min_overlap)
    if overlap:
        return s2 + s1[overlap:]

    return None


def coalesce_fragments(fragments: List[str], min_overlap: int = 10) -> List[str]:
    """
    Coalesce overlapping string fragments into merged strings.

    Iteratively merges overlapping fragments until no more merges are possible.
    Fragments that don't overlap with any others are returned unchanged.

    Args:
        fragments: List of string fragments that may overlap
        min_overlap: Minimum character overlap required for merging

    Returns:
        List of coalesced strings (may be shorter than input)
    """
    if not fragments:
        return []

    if len(fragments) == 1:
        return fragments.copy()

    # Work with a mutable list
    working = list(fragments)
    changed = True

    while changed:
        changed = False
        new_working = []
        used = set()

        for i in range(len(working)):
            if i in used:
                continue

            current = working[i]
            merged = False

            for j in range(i + 1, len(working)):
                if j in used:
                    continue

                result = merge_two_strings(current, working[j], min_overlap)
                if result:
                    new_working.append(result)
                    used.add(i)
                    used.add(j)
                    changed = True
                    merged = True
                    break

            if not merged:
                new_working.append(current)
                used.add(i)

        working = new_working

    return working


def coalesce_verbatim_groups(
    verbatim_groups: Dict[str, Dict],
    case_sensitive: bool = False,
    min_overlap: int = 10
) -> Dict[str, Dict]:
    """
    Coalesce overlapping verbatim fragments within groups sharing the same tinyId set.

    Fragments are grouped by their tinyId set, then coalesced within each group.
    This handles the case where sliding window extraction produces overlapping
    fragments from the same source documents.

    Args:
        verbatim_groups: Dict mapping verbatim_text -> {"count": int, "tinyids": set}
        case_sensitive: Use case-sensitive comparison for overlap detection
        min_overlap: Minimum character overlap required for merging

    Returns:
        New dict with coalesced verbatim groups
    """
    if not verbatim_groups:
        return {}

    # Group fragments by their tinyId set (frozen for hashing)
    tinyid_groups: Dict[frozenset, List[Tuple[str, Dict]]] = defaultdict(list)
    for verbatim, data in verbatim_groups.items():
        key = frozenset(data["tinyids"])
        tinyid_groups[key].append((verbatim, data))

    result = {}

    for tinyid_set, fragments_with_data in tinyid_groups.items():
        if len(fragments_with_data) == 1:
            # Single fragment, keep as-is
            verbatim, data = fragments_with_data[0]
            result[verbatim] = data
            continue

        # Extract just the strings for coalescing
        fragments = [v for v, _ in fragments_with_data]

        # Build count map for aggregating counts after coalescing
        count_map = {v: d["count"] for v, d in fragments_with_data}

        # Prepare fragments for comparison (case handling)
        if case_sensitive:
            compare_fragments = fragments
        else:
            compare_fragments = [f.lower() for f in fragments]

        # Coalesce using lowercase for comparison but track original forms
        # Map lowercase -> list of original forms
        lower_to_originals: Dict[str, List[str]] = defaultdict(list)
        for frag in fragments:
            lower_to_originals[frag.lower()].append(frag)

        # Coalesce the lowercase versions
        unique_lower = list(set(compare_fragments))
        coalesced_lower = coalesce_fragments(unique_lower, min_overlap)

        # For each coalesced result, find which original fragments were merged
        for coalesced in coalesced_lower:
            # Find all original fragments that are substrings of or contributed to this result
            merged_originals = []
            total_count = 0

            for orig_frag in fragments:
                orig_lower = orig_frag.lower()
                # Check if this fragment was part of the coalesced result
                if orig_lower in coalesced or coalesced in orig_lower:
                    merged_originals.append(orig_frag)
                    total_count += count_map[orig_frag]
                elif find_overlap(orig_lower, coalesced, min_overlap) or find_overlap(coalesced, orig_lower, min_overlap):
                    merged_originals.append(orig_frag)
                    total_count += count_map[orig_frag]

            if not merged_originals:
                # Fallback: just use the coalesced form
                # Find longest original that matches
                for orig_frag in fragments:
                    if orig_frag.lower() == coalesced:
                        merged_originals.append(orig_frag)
                        total_count += count_map[orig_frag]
                        break

            # Use the longest original form that's part of this coalescence
            # or reconstruct from the coalesced lowercase
            if merged_originals:
                # Pick the longest original as the representative
                best_original = max(merged_originals, key=len)
                # But if coalesced is longer, we need to build it
                if len(coalesced) > len(best_original):
                    # Use coalesced but try to preserve case from originals
                    representative = _reconstruct_case(coalesced, merged_originals)
                else:
                    representative = best_original
            else:
                representative = coalesced

            result[representative] = {
                "count": total_count if total_count > 0 else 1,
                "tinyids": set(tinyid_set)
            }

    return result


def _reconstruct_case(coalesced_lower: str, originals: List[str]) -> str:
    """
    Attempt to reconstruct proper casing from original fragments.

    Uses the longest original as the base and extends with coalesced content.

    Args:
        coalesced_lower: Lowercase coalesced string
        originals: Original cased fragments

    Returns:
        Best-effort case-preserved string
    """
    if not originals:
        return coalesced_lower

    # Sort by length descending
    sorted_originals = sorted(originals, key=len, reverse=True)
    longest = sorted_originals[0]

    # If longest already matches coalesced length, use it
    if len(longest) >= len(coalesced_lower):
        return longest

    # Try to extend longest with content from coalesced
    # Find where longest ends in coalesced
    longest_lower = longest.lower()
    if longest_lower in coalesced_lower:
        start_idx = coalesced_lower.find(longest_lower)
        end_idx = start_idx + len(longest_lower)

        # Build result: prefix from coalesced + longest + suffix from coalesced
        prefix = coalesced_lower[:start_idx]
        suffix = coalesced_lower[end_idx:]

        return prefix + longest + suffix

    return coalesced_lower
