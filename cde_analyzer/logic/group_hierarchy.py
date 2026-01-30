#
# File: logic/group_hierarchy.py
#
"""
Group/sub-group hierarchy assignment for instrument patterns.

Assigns a two-level hierarchy to coalesced patterns:
- **group**: Main instrument name (e.g., "PROMIS"), with trailing delimiters stripped
- **sub_group**: Full pattern = specific variant (e.g., "PROMIS - Sleep Disturbance")
- **suffix**: Distinguishing part after the shared prefix (e.g., "Sleep Disturbance")

This enables three substitution strategies:
1. Sub-group substitution (specific sub-instrument)
2. Group-only substitution (main instrument name)
3. Both (two-pass: sub-group first, then group catches remaining)

Usage:
    from logic.group_hierarchy import build_group_hierarchy

    assignments, stats = build_group_hierarchy(pattern_to_tinyids)
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from utils.logger import logging

logger = logging.getLogger(__name__)

# Trailing delimiters to strip from group names.
# Matches sequences of hyphens, colons, semicolons, commas, dots, and whitespace.
_TRAILING_DELIM_RE = re.compile(r'[\s\-:;,.]+$')
_LEADING_DELIM_RE = re.compile(r'^[\s\-:;,.]+')


@dataclass
class GroupAssignment:
    """Assignment of a pattern to a group/sub-group hierarchy."""
    group: str              # cleaned main instrument name (e.g., "PROMIS")
    sub_group: str          # full pattern (e.g., "PROMIS - Sleep Disturbance")
    suffix: str             # distinguishing part after prefix (e.g., "Sleep Disturbance")
    tinyids: Set[str] = field(default_factory=set)
    group_size: int = 0     # number of patterns in this group
    group_tinyid_count: int = 0  # total unique tinyIds across group


def strip_trailing_delimiters(name: str) -> str:
    """
    Strip trailing punctuation/delimiters from a group name.

    Examples:
        "PROMIS -"  → "PROMIS"
        "Score -"   → "Score"
        "CES-D -"   → "CES-D"
        "  - stuff"  → "stuff"
    """
    result = _TRAILING_DELIM_RE.sub('', name)
    result = _LEADING_DELIM_RE.sub('', result)
    return result.strip()


def _extract_suffix(pattern: str, prefix: str) -> str:
    """Extract the suffix portion of a pattern after the shared prefix."""
    if not prefix or not pattern.startswith(prefix):
        return ""
    remainder = pattern[len(prefix):]
    return strip_trailing_delimiters(remainder) if remainder else ""


def build_group_hierarchy(
    patterns_with_tinyids: Dict[str, Set[str]],
    min_group_size: int = 2,
    min_prefix_words: int = 2
) -> Tuple[List[GroupAssignment], Dict[str, int]]:
    """
    Assign group/sub-group hierarchy to patterns based on shared prefixes.

    Reuses build_prefix_groups() from span_boundary for prefix grouping,
    then strips trailing delimiters from prefixes to get clean group names.
    Groups that collapse to the same cleaned name are merged.

    Args:
        patterns_with_tinyids: Dict mapping pattern -> set of tinyIds.
        min_group_size: Minimum patterns per group.
        min_prefix_words: Minimum words in shared prefix to form a group.

    Returns:
        Tuple of:
        - List of GroupAssignment objects (one per pattern, including ungrouped)
        - Stats dict with counts
    """
    from logic.span_boundary import build_prefix_groups

    patterns = list(patterns_with_tinyids.keys())

    # Stage 1: Build raw prefix groups
    raw_groups = build_prefix_groups(patterns, min_group_size, min_prefix_words)
    logger.info(f"Prefix grouping: {len(raw_groups)} raw groups from {len(patterns)} patterns")

    # Stage 2: Clean group names (strip delimiters) and merge collisions
    # cleaned_group_name -> {raw_prefix, patterns, merged_tinyids}
    merged_groups: Dict[str, Dict] = {}

    for raw_prefix, group_patterns in raw_groups.items():
        cleaned = strip_trailing_delimiters(raw_prefix)
        if not cleaned:
            cleaned = raw_prefix  # fallback: don't lose the group

        if cleaned not in merged_groups:
            merged_groups[cleaned] = {
                'raw_prefixes': [raw_prefix],
                'patterns': list(group_patterns),
                'tinyids': set(),
            }
        else:
            merged_groups[cleaned]['raw_prefixes'].append(raw_prefix)
            merged_groups[cleaned]['patterns'].extend(group_patterns)

        for pat in group_patterns:
            merged_groups[cleaned]['tinyids'].update(
                patterns_with_tinyids.get(pat, set())
            )

    # Deduplicate patterns within each group
    for group_data in merged_groups.values():
        group_data['patterns'] = list(dict.fromkeys(group_data['patterns']))

    # Filter groups below min_group_size after merging
    merged_groups = {
        name: data for name, data in merged_groups.items()
        if len(data['patterns']) >= min_group_size
    }

    logger.info(
        f"After delimiter stripping: {len(merged_groups)} groups "
        f"(merged from {len(raw_groups)} raw prefix groups)"
    )

    # Stage 3: Build assignments
    grouped_patterns: Set[str] = set()
    assignments: List[GroupAssignment] = []

    for group_name, group_data in sorted(merged_groups.items()):
        group_pats = group_data['patterns']
        group_tinyids = group_data['tinyids']
        group_size = len(group_pats)
        group_tid_count = len(group_tinyids)

        # Find the longest raw prefix for suffix extraction
        longest_prefix = max(group_data['raw_prefixes'], key=len)

        for pat in group_pats:
            suffix = _extract_suffix(pat, longest_prefix)
            assignments.append(GroupAssignment(
                group=group_name,
                sub_group=pat,
                suffix=suffix,
                tinyids=patterns_with_tinyids.get(pat, set()),
                group_size=group_size,
                group_tinyid_count=group_tid_count,
            ))
            grouped_patterns.add(pat)

    # Add ungrouped patterns
    ungrouped_count = 0
    for pat in patterns:
        if pat not in grouped_patterns:
            assignments.append(GroupAssignment(
                group="",
                sub_group=pat,
                suffix="",
                tinyids=patterns_with_tinyids.get(pat, set()),
                group_size=0,
                group_tinyid_count=0,
            ))
            ungrouped_count += 1

    stats = {
        'total_patterns': len(patterns),
        'groups': len(merged_groups),
        'grouped_patterns': len(grouped_patterns),
        'ungrouped_patterns': ungrouped_count,
    }

    logger.info(
        f"Hierarchy: {len(merged_groups)} groups, "
        f"{len(grouped_patterns)} grouped, {ungrouped_count} ungrouped"
    )

    return assignments, stats


def detect_abbreviation_variants(groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Detect patterns sharing a common abbreviation stem.

    Stub for future refinement: e.g., PROMIS-SF, PROMIS-29 share stem PROMIS.

    Args:
        groups: Dict mapping group name -> list of patterns.

    Returns:
        Dict mapping abbreviation stem -> list of variant patterns.
        Currently returns empty dict (placeholder).
    """
    # Future: analyze character-level similarity of group names
    # to detect abbreviation families (e.g., PROMIS, PROMIS-SF, PROMIS-29)
    return {}
