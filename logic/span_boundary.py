#
# File: logic/span_boundary.py
#
"""
Semantic span boundary detection for pattern grouping.

Groups patterns by shared prefix spans, then uses SpaCy POS + dependency
parsing to trim span boundaries back to the last semantically meaningful
token. This prevents shared spans from overshooting into content-bearing
tokens (e.g., "in the past 7 days I" → "in the past 7 days").

Four-stage approach:
1. Word-level prefix grouping (longest common prefix among sorted patterns)
2. SpaCy POS-based trim of trailing function words
3. Merge groups that collapse to the same trimmed prefix
4. Classify groups by semantic type (temporal, etc.) for super-grouping
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from utils.logger import logging

logger = logging.getLogger(__name__)

# POS tags that should be trimmed from the trailing edge of a shared span.
# These are function words that syntactically attach left but semantically
# belong to the content clause that follows.
_TRIM_POS = {"PRON", "DET", "CCONJ", "SCONJ", "PART", "PUNCT"}


@dataclass
class SemanticGroup:
    """A group of patterns sharing a semantically trimmed prefix."""
    trimmed_prefix: str
    patterns: List[str]
    merged_tinyids: Set[str] = field(default_factory=set)
    super_group: str = ""  # e.g., "temporal" classifier label


def _longest_common_prefix_words(a: str, b: str) -> List[str]:
    """Return the longest common word-prefix between two strings."""
    words_a = a.split()
    words_b = b.split()
    prefix = []
    for wa, wb in zip(words_a, words_b):
        if wa == wb:
            prefix.append(wa)
        else:
            break
    return prefix


def build_prefix_groups(
    patterns: List[str],
    min_group_size: int = 2,
    min_prefix_words: int = 2
) -> Dict[str, List[str]]:
    """
    Group patterns by their longest common word-prefix.

    Sorts patterns lexicographically, then computes LCP between adjacent
    pairs. Patterns sharing a prefix of >= min_prefix_words are grouped.

    Args:
        patterns: List of pattern strings.
        min_group_size: Minimum patterns per group to include.
        min_prefix_words: Minimum words in prefix to form a group.

    Returns:
        Dict mapping prefix string -> list of patterns sharing that prefix.
    """
    if not patterns:
        return {}

    sorted_patterns = sorted(patterns)

    # Build adjacency LCPs
    # For each pair of adjacent sorted patterns, compute their LCP.
    # Then greedily extend groups.
    groups: Dict[str, List[str]] = {}
    i = 0
    while i < len(sorted_patterns):
        # Start a new potential group with pattern[i]
        current = sorted_patterns[i]
        if i + 1 >= len(sorted_patterns):
            # Last pattern, no neighbor to group with
            i += 1
            continue

        # Compute LCP with next pattern
        lcp = _longest_common_prefix_words(current, sorted_patterns[i + 1])
        if len(lcp) < min_prefix_words:
            i += 1
            continue

        # Found a group seed. Extend to include all patterns sharing this prefix.
        prefix_str = " ".join(lcp)
        group = [current]

        j = i + 1
        while j < len(sorted_patterns):
            candidate_lcp = _longest_common_prefix_words(current, sorted_patterns[j])
            # Narrow the prefix to the LCP of the whole group
            narrowed = _longest_common_prefix_words(prefix_str, " ".join(candidate_lcp))
            if len(narrowed) >= min_prefix_words:
                prefix_str = " ".join(narrowed)
                group.append(sorted_patterns[j])
                j += 1
            else:
                break

        if len(group) >= min_group_size:
            # Re-compute the true LCP across the whole group
            group_lcp_words = group[0].split()
            for pat in group[1:]:
                group_lcp_words = _longest_common_prefix_words(
                    " ".join(group_lcp_words), pat
                )
                if len(group_lcp_words) < min_prefix_words:
                    break

            if len(group_lcp_words) >= min_prefix_words:
                final_prefix = " ".join(group_lcp_words)
                if final_prefix in groups:
                    groups[final_prefix].extend(group)
                else:
                    groups[final_prefix] = group

        i = j

    return groups


def trim_span_boundary(span: str, nlp, representative_pattern: str = "") -> str:
    """
    Trim trailing function words from a shared span using SpaCy POS tagging.

    To avoid mis-parsing fragments (e.g., "During the" parsed without the
    noun "past" that "the" modifies), we parse a representative full pattern
    and check POS tags at the prefix boundary position within full context.

    Trim rules (right-to-left from end of prefix within full parse):
    - POS in {PRON, DET, CCONJ, SCONJ, PART, PUNCT} → trim
    - POS=ADP where the token has no children within the prefix → trim
    - Stops at first non-trimmable token (NOUN, VERB, NUM, ADJ, PROPN, ADV)

    Args:
        span: The candidate shared span string.
        nlp: A loaded SpaCy language model.
        representative_pattern: A full pattern from the group, used for
            context-aware parsing. If empty, parses the span alone.

    Returns:
        Trimmed span string.
    """
    if not span or not span.strip():
        return span

    span_words = span.split()
    prefix_len = len(span_words)

    # Parse in context of full pattern for better POS accuracy
    parse_text = representative_pattern if representative_pattern else span
    doc = nlp(parse_text)
    tokens = list(doc)

    # Find the prefix boundary: map word-level prefix to token positions.
    # SpaCy may tokenize differently (e.g., "Neuro-QOL" → 3 tokens).
    # Walk tokens and match words greedily.
    word_idx = 0
    prefix_token_end = 0
    reconstructed = ""
    for i, token in enumerate(tokens):
        if word_idx >= prefix_len:
            break
        # Check if current token text matches start of current word
        current_word = span_words[word_idx]
        reconstructed += token.text_with_ws
        # Check if we've consumed the current word
        clean = reconstructed.strip()
        if clean.endswith(current_word) or current_word.startswith(token.text):
            # Heuristic: if reconstructed text covers word, advance
            pass
        prefix_token_end = i + 1
        # Advance word index when whitespace follows (rough alignment)
        stripped_so_far = "".join(t.text_with_ws for t in tokens[:i + 1]).rstrip()
        matched_words = stripped_so_far.split()
        word_idx = len(matched_words)

    if prefix_token_end <= 0:
        return span

    prefix_tokens = tokens[:prefix_token_end]

    # Trim from right
    trim_end = len(prefix_tokens)
    for i in range(len(prefix_tokens) - 1, -1, -1):
        token = prefix_tokens[i]
        if token.pos_ in _TRIM_POS:
            trim_end = i
        elif token.pos_ == "ADP":
            # Only trim trailing ADP if it has no pobj children within prefix
            children_in_prefix = [c for c in token.children if c.i < prefix_token_end]
            content_children = [c for c in children_in_prefix
                                if c.pos_ not in _TRIM_POS and c.pos_ != "ADP"]
            if not content_children:
                trim_end = i
            else:
                break
        else:
            break

    if trim_end <= 0:
        logger.debug(f"Trim would remove all tokens from '{span}', keeping original")
        return span

    trimmed_tokens = prefix_tokens[:trim_end]
    result = "".join(t.text_with_ws for t in trimmed_tokens).rstrip()
    return result


# --- Semantic classifiers for group prefixes ---

# Number words for temporal quantifier matching
_NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "sixty", "ninety",
}

# Temporal frame regex: matches prefixes like "in the past 7 days"
# Structure: [prep] the [past|last] [N] [time_unit]
# N can be arabic numeral, number word, or absent (implied "one")
_TEMPORAL_FRAME_RE = re.compile(
    r"^(?:in|over|during|for|within)\s+the\s+(?:past|last)\s+"
    r"(?:(?:\d+|" + "|".join(_NUMBER_WORDS) + r")\s+)?"
    r"(?:days?|weeks?|months?|years?)"
    r"(?:\s*,)?$",  # optional trailing comma
    re.IGNORECASE,
)


def classify_group(prefix: str, patterns: List[str]) -> str:
    """
    Classify a group into a semantic super-group.

    Checks both the group prefix and the patterns themselves.
    A group is "temporal" if:
    - The prefix itself matches the full temporal frame, OR
    - The prefix is a partial temporal frame AND most patterns
      start with a full temporal frame.

    Currently supports:
    - "temporal": temporal frame boilerplate

    Returns empty string if no classification matches.
    """
    prefix_clean = prefix.strip()

    # Direct match: prefix is a full temporal frame
    if _TEMPORAL_FRAME_RE.match(prefix_clean):
        return "temporal"

    # Partial match: prefix is the beginning of a temporal frame
    # Could be "In the past", "Over the", "in the", "the past", etc.
    partial_temporal = re.match(
        r"^(?:"
        r"(?:in|over|during|for|within)\s+the(?:\s+(?:past|last))?"
        r"|the\s+(?:past|last)"
        r"|past\s+\d"  # "past 7" (rare but possible)
        r")\s*$",
        prefix_clean,
        re.IGNORECASE,
    )
    if partial_temporal and patterns:
        # Check if majority of patterns contain temporal frame evidence.
        # Use a lenient check: pattern contains [prep] the [past|last]
        # or starts with "the past/last" (the full frame may be truncated
        # in coalesced patterns)
        _temporal_evidence = re.compile(
            r"(?:(?:in|over|during|for|within)\s+)?the\s+(?:past|last)\b",
            re.IGNORECASE,
        )
        temporal_count = sum(
            1 for p in patterns if _temporal_evidence.search(p)
        )
        # Require higher confidence for short/ambiguous prefixes
        # (e.g., "in the" could be temporal or locative)
        has_past_last = re.search(r"\b(?:past|last)\b", prefix_clean, re.IGNORECASE)
        threshold = 0.5 if has_past_last else 0.9
        if temporal_count >= len(patterns) * threshold:
            return "temporal"

    return ""


def _extract_temporal_frame(text: str) -> str:
    """Extract the temporal frame portion from a text string, or empty if none."""
    words = text.split()
    for n in range(min(len(words), 8), 2, -1):
        candidate = " ".join(words[:n])
        if _TEMPORAL_FRAME_RE.match(candidate):
            return candidate
    return ""


# Regex to strip quantifier from temporal frame, leaving prep + det + adj + unit
_QUANTIFIER_RE = re.compile(
    r"(?P<prefix>(?:in|over|during|for|within)\s+the\s+(?:past|last)\s+)"
    r"(?:(?:\d+|" + "|".join(_NUMBER_WORDS) + r")\s+)"
    r"(?P<unit>(?:days?|weeks?|months?|years?)(?:\s*,)?)",
    re.IGNORECASE,
)


def generate_temporal_no_quantifier(frame: str) -> str:
    """Generate the implied-ONE form of a temporal frame.

    Strips the numeric quantifier and singularizes the time unit:
        "In the past 7 days" → "In the past day"
        "Over the last 2 weeks" → "Over the last week"

    Returns empty string if the frame has no quantifier (already implied-ONE)
    or doesn't match the temporal pattern.
    """
    m = _QUANTIFIER_RE.match(frame.strip())
    if not m:
        return ""
    prefix = m.group("prefix")
    unit = m.group("unit").rstrip(",").rstrip()
    # Singularize: days→day, weeks→week, months→month, years→year
    if unit.endswith("s"):
        unit = unit[:-1]
    return prefix + unit


def normalize_temporal_prefix(prefix: str, patterns: List[str] = None) -> str:
    """
    Normalize a temporal prefix to a canonical form for super-grouping.

    Replaces the quantifier with 'N' and lowercases, so that
    "In the past 7 days" and "In the past 30 days" collapse to
    "in the past N days".

    If the prefix is partial (e.g., "In the past"), extracts the full
    temporal frame from a representative pattern.

    Returns the normalized string, or the original lowercased prefix
    if it doesn't match the temporal pattern.
    """
    # Try direct match on prefix first
    frame = _extract_temporal_frame(prefix)

    # If prefix is partial, try extracting from a representative pattern
    if not frame and patterns:
        for pat in patterns:
            frame = _extract_temporal_frame(pat)
            if frame:
                break

    # If no full frame found, try matching "the past/last N unit" directly
    # (for groups where the LCP is "the past" without leading preposition)
    if not frame:
        _partial_frame_re = re.compile(
            r"^(the\s+(?:past|last)\s+)"
            r"(?:(?:\d+|" + "|".join(_NUMBER_WORDS) + r")\s+)?"
            r"((?:days?|weeks?|months?|years?))",
            re.IGNORECASE,
        )
        candidates = [prefix] + (patterns or [])
        for text in candidates:
            m2 = _partial_frame_re.match(text.strip())
            if m2:
                det_part = m2.group(1).lower().strip()
                unit_part = m2.group(2).lower().strip()
                if not unit_part.endswith("s"):
                    unit_part += "s"
                return f"{det_part} N {unit_part}"
        return prefix.lower()

    m = re.match(
        r"^((?:in|over|during|for|within)\s+the\s+(?:past|last)\s+)"
        r"(?:(?:\d+|" + "|".join(_NUMBER_WORDS) + r")\s+)?"
        r"((?:days?|weeks?|months?|years?)(?:\s*,)?)\s*$",
        frame.strip(),
        re.IGNORECASE,
    )
    if m:
        prep_part = m.group(1).lower().strip()
        unit_part = m.group(2).lower().strip().rstrip(",")
        # Normalize plural: always use plural form
        if not unit_part.endswith("s"):
            unit_part += "s"
        return f"{prep_part} N {unit_part}"
    return prefix.lower()


def group_patterns_semantic(
    patterns_with_tinyids: Dict[str, Set[str]],
    nlp,
    min_group_size: int = 2,
    min_prefix_words: int = 2
) -> Tuple[List[SemanticGroup], List[str]]:
    """
    Group patterns by semantically trimmed shared prefixes.

    Pipeline:
    1. Build word-level prefix groups from pattern list
    2. Trim each group's prefix using SpaCy POS analysis
    3. Merge groups that collapse to the same trimmed prefix

    Args:
        patterns_with_tinyids: Dict mapping pattern -> set of tinyIds.
        nlp: Loaded SpaCy language model.
        min_group_size: Minimum patterns per group.
        min_prefix_words: Minimum words in shared prefix.

    Returns:
        Tuple of:
        - List of SemanticGroup objects (grouped patterns)
        - List of ungrouped pattern strings
    """
    patterns = list(patterns_with_tinyids.keys())

    # Stage 1: Build raw prefix groups
    raw_groups = build_prefix_groups(patterns, min_group_size, min_prefix_words)
    logger.info(f"Stage 1: {len(raw_groups)} raw prefix groups from {len(patterns)} patterns")

    # Stage 2: Trim each prefix with SpaCy (using longest pattern as context)
    trimmed_groups: Dict[str, List[str]] = {}
    for raw_prefix, group_patterns in raw_groups.items():
        # Use longest pattern for context-aware parsing
        representative = max(group_patterns, key=len)
        trimmed = trim_span_boundary(raw_prefix, nlp, representative_pattern=representative)
        if not trimmed:
            trimmed = raw_prefix

        if trimmed in trimmed_groups:
            trimmed_groups[trimmed].extend(group_patterns)
        else:
            trimmed_groups[trimmed] = list(group_patterns)

        if trimmed != raw_prefix:
            logger.debug(f"Trimmed: '{raw_prefix}' -> '{trimmed}'")

    logger.info(
        f"Stage 2: {len(trimmed_groups)} groups after SpaCy trim "
        f"(merged {len(raw_groups) - len(trimmed_groups)} groups)"
    )

    # Stage 3: Build SemanticGroup objects with merged tinyIds
    grouped_patterns = set()
    result_groups = []

    for prefix, group_pats in sorted(trimmed_groups.items()):
        # Deduplicate patterns within group
        unique_pats = list(dict.fromkeys(group_pats))

        if len(unique_pats) < min_group_size:
            continue

        merged_tinyids = set()
        for pat in unique_pats:
            merged_tinyids.update(patterns_with_tinyids.get(pat, set()))

        result_groups.append(SemanticGroup(
            trimmed_prefix=prefix,
            patterns=unique_pats,
            merged_tinyids=merged_tinyids
        ))
        grouped_patterns.update(unique_pats)

    # Collect ungrouped patterns (preserve original order)
    ungrouped = [p for p in patterns if p not in grouped_patterns]

    logger.info(
        f"Stage 3: {len(result_groups)} semantic groups "
        f"({len(grouped_patterns)} grouped, {len(ungrouped)} ungrouped)"
    )

    # Stage 4: Classify groups by semantic type (e.g., temporal)
    temporal_count = 0
    for group in result_groups:
        label = classify_group(group.trimmed_prefix, group.patterns)
        if label:
            group.super_group = label
            temporal_count += 1

    if temporal_count:
        logger.info(f"Stage 4: {temporal_count} groups classified as temporal")

    return result_groups, ungrouped
