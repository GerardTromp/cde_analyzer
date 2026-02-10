"""
Context-aware masking for instrument detection.

Option D implementation: Instead of exact pattern matching, this approach:
1. Finds context phrases like "as part of", "based on", etc.
2. Looks for known instrument names after the context phrase
3. Masks the entire span from context start through the end of instrument reference
   (including suffixes like "for Pesticides (Work)")

This handles cases where exact patterns fail due to:
- Unknown acronym variants (RFQ vs RFQ-U)
- Suffix content after first acronym
- Spacing/punctuation variations
"""

import re
import logging
from typing import List, Tuple, Set, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Context phrases that introduce instrument references
CONTEXT_PHRASES = [
    r'as\s+a?\s*part\s+of\s+(?:the\s+)?',   # "as part of", "as a part of", "as part of the"
    r'based\s+on\s+(?:the\s+)?',             # "based on", "based on the"
    r'from\s+(?:the\s+)?',                   # "from", "from the"
    r'using\s+(?:the\s+)?',                  # "using", "using the"
    r'administered\s+(?:the\s+)?',           # "administered", "administered the"
    r'completed\s+(?:the\s+)?',              # "completed", "completed the"
    r'per\s+(?:the\s+)?',                    # "per", "per the"
    r'according\s+to\s+(?:the\s+)?',         # "according to", "according to the"
    r'measured\s+(?:by|with|using)\s+(?:the\s+)?',  # "measured by/with/using"
]

# Compile combined context pattern
CONTEXT_PATTERN = re.compile(
    r'(' + '|'.join(CONTEXT_PHRASES) + r')',
    re.IGNORECASE
)

# Pattern to match end of instrument reference
# Matches: Instrument Name (ACRONYM) optional-suffix (OPTIONAL-ACRONYM) ...
# Continues until we hit certain stop words or sentence boundaries
INSTRUMENT_END_PATTERN = re.compile(
    r'[A-Z][^.!?]*?'  # Start with capital, continue non-sentence-ending
    r'(?:\s*\([A-Za-z0-9\-]+\))?'  # Optional first acronym
    r'(?:'  # Optional suffix group
    r'\s+(?:for|in|of|about|regarding|related to|concerning)'  # Suffix connectors
    r'\s+[A-Z][^.!?]*?'  # Suffix content
    r'(?:\s*\([A-Za-z0-9\-]+\))?'  # Optional suffix acronym
    r')*'  # Allow multiple suffix groups
    r'(?=\s*[.,;:!?]|\s*$|\s+(?:and|or|but|which|that|to)\s)',  # End markers
    re.IGNORECASE
)

# Simpler pattern that just captures until common terminators
INSTRUMENT_SPAN_SIMPLE = re.compile(
    r'([A-Z][A-Za-z0-9\s\-\(\)]+?)'  # Instrument text
    r'(?=\s*[.,;:!?\n]|\s+(?:and|or|but|which|that|The|A|An|This|These|In|On|At|For|If|When|While|After|Before|During|To|From|With|By|As|Is|Are|Was|Were|Has|Have|Had|Can|Could|May|Might|Must|Should|Would|Will)\s|$)',
    re.MULTILINE
)


@dataclass
class ContextMatch:
    """A matched instrument reference with context."""
    context_start: int      # Character start of context phrase
    context_end: int        # Character end of context phrase
    instrument_start: int   # Character start of instrument name
    instrument_end: int     # Character end of entire instrument span
    context_phrase: str     # The context phrase (e.g., "as part of the ")
    instrument_span: str    # The full instrument span text
    matched_name: str       # The known instrument name that matched


def normalize_instrument_name(name: str) -> str:
    """Normalize instrument name for matching."""
    # Lowercase, collapse whitespace
    normalized = ' '.join(name.lower().split())
    return normalized


def extract_instrument_names_from_patterns(patterns: Set[str]) -> Dict[str, str]:
    """
    Extract bare instrument names from full patterns.

    Args:
        patterns: Set of patterns like "as part of the Risk Factor Questionnaire (RFQ)"

    Returns:
        Dict mapping normalized_name → original_name (most common casing)
    """
    from utils.pattern_variant_generator import extract_instrument_name_and_acronym

    name_counts: Dict[str, Dict[str, int]] = {}  # normalized → {original → count}

    for pattern in patterns:
        prefix, name, acronym = extract_instrument_name_and_acronym(pattern)
        if name:
            norm = normalize_instrument_name(name)
            if norm not in name_counts:
                name_counts[norm] = {}
            name_counts[norm][name] = name_counts[norm].get(name, 0) + 1

    # Select most common casing for each normalized name
    result = {}
    for norm, originals in name_counts.items():
        best = max(originals.items(), key=lambda x: x[1])[0]
        result[norm] = best

    return result


def find_context_aware_matches(
    text: str,
    instrument_names: Dict[str, str]
) -> List[ContextMatch]:
    """
    Find instrument references using context-aware matching.

    Args:
        text: The text to search
        instrument_names: Dict of normalized_name → original_name

    Returns:
        List of ContextMatch objects
    """
    matches = []
    text_lower = text.lower()

    # Find all context phrase occurrences
    for context_match in CONTEXT_PATTERN.finditer(text):
        context_start = context_match.start()
        context_end = context_match.end()
        context_phrase = context_match.group(0)

        # Look for any known instrument name starting after the context phrase
        search_start = context_end
        search_region = text_lower[search_start:]

        best_match = None
        best_match_len = 0

        for norm_name, orig_name in instrument_names.items():
            # Find if this instrument name appears at or near the start
            idx = search_region.find(norm_name)
            if idx == -1:
                continue

            # Only accept if it starts within first few words (some preamble allowed)
            # Count words before the match
            preamble = search_region[:idx]
            preamble_words = len(preamble.split())

            if preamble_words > 5:  # Allow up to 5 words of preamble (version numbers, etc.)
                continue

            # Found a match - now find the full extent of the instrument span
            name_start = search_start + idx
            name_end = name_start + len(norm_name)

            # Extend to include trailing content (acronyms, suffixes)
            instrument_span_end = extend_instrument_span(text, name_end)

            match_len = instrument_span_end - context_start
            if match_len > best_match_len:
                best_match_len = match_len
                best_match = ContextMatch(
                    context_start=context_start,
                    context_end=context_end,
                    instrument_start=name_start,
                    instrument_end=instrument_span_end,
                    context_phrase=context_phrase,
                    instrument_span=text[name_start:instrument_span_end],
                    matched_name=orig_name
                )

        if best_match:
            matches.append(best_match)

    return matches


def extend_instrument_span(text: str, start_pos: int) -> int:
    """
    Extend from after the instrument name to capture acronyms and suffixes.

    Captures patterns like:
    - " (ACRONYM)" → ends after ")"
    - " (ACRONYM) for Something (SUFFIX)" → ends after last ")"
    - " (ACRONYM) for Something" → ends after "Something"

    Args:
        text: Full text
        start_pos: Position after the instrument name

    Returns:
        End position of the full instrument span
    """
    pos = start_pos
    text_len = len(text)

    # Skip trailing whitespace
    while pos < text_len and text[pos] in ' \t':
        pos += 1

    # Look for parenthetical (acronym)
    while pos < text_len:
        # Handle opening parenthesis for acronym
        if text[pos] == '(':
            # Find matching close
            depth = 1
            pos += 1
            while pos < text_len and depth > 0:
                if text[pos] == '(':
                    depth += 1
                elif text[pos] == ')':
                    depth -= 1
                pos += 1
            # pos now points after ')'

            # Skip trailing whitespace
            while pos < text_len and text[pos] in ' \t':
                pos += 1

            # Check for suffix continuation words
            suffix_words = ['for', 'in', 'of', 'about', 'regarding', 'related', 'concerning']
            found_suffix = False
            for word in suffix_words:
                if text_len > pos + len(word) and text[pos:pos + len(word)].lower() == word:
                    # Check it's a word boundary
                    if pos + len(word) >= text_len or not text[pos + len(word)].isalnum():
                        # Found suffix word - continue parsing
                        pos += len(word)
                        while pos < text_len and text[pos] in ' \t':
                            pos += 1
                        # Now look for the suffix content
                        # Read words until we hit a sentence ender or another context word
                        while pos < text_len:
                            if text[pos] in '.!?;:\n':
                                break
                            if text[pos] == '(':
                                # Another parenthetical - handle it in next loop iteration
                                found_suffix = True
                                break
                            # Check for stop words
                            remaining = text[pos:].lower()
                            stop_found = False
                            for stop in [' and ', ' or ', ' but ', ' which ', ' that ', ' the ', ' a ', ' an ']:
                                if remaining.startswith(stop[1:]):  # Skip leading space
                                    stop_found = True
                                    break
                            if stop_found:
                                break
                            pos += 1
                        found_suffix = True
                        break

            if not found_suffix:
                # No suffix word found, we're done
                break
        else:
            # No more parentheses, we're done
            break

    # Trim trailing whitespace/punctuation that shouldn't be included
    while pos > start_pos and text[pos - 1] in ' \t':
        pos -= 1

    return pos


def compute_context_aware_mask_ranges(
    text: str,
    char_offsets: List[Tuple[int, int]],
    instrument_names: Dict[str, str],
    old_to_new_index: Optional[Dict[int, int]] = None
) -> List[Tuple[int, int, str]]:
    """
    Compute token ranges to mask using context-aware matching.

    Args:
        text: Original text
        char_offsets: List of (start, end) character positions per token
        instrument_names: Dict of normalized_name → original_name
        old_to_new_index: Optional mapping from original to post-stopword token indices

    Returns:
        List of (token_start, token_end, mask_key) tuples
    """
    matches = find_context_aware_matches(text, instrument_names)
    mask_ranges = []

    for match in matches:
        # Find token range that covers the match span
        # We want to mask from context_start to instrument_end
        char_start = match.context_start
        char_end = match.instrument_end

        token_start = None
        token_end = None

        for ti, (cs, ce) in enumerate(char_offsets):
            # Token overlaps if it starts before span ends AND ends after span starts
            if cs < char_end and ce > char_start:
                if token_start is None:
                    token_start = ti
                token_end = ti + 1

        if token_start is not None and token_end is not None:
            # Translate indices if stopwords were removed
            if old_to_new_index is not None:
                new_start = None
                new_end = None
                for old_idx in range(token_start, token_end):
                    if old_idx in old_to_new_index:
                        new_idx = old_to_new_index[old_idx]
                        if new_start is None:
                            new_start = new_idx
                        new_end = new_idx + 1
                if new_start is not None and new_end is not None:
                    token_start = new_start
                    token_end = new_end
                else:
                    continue  # All tokens were stopwords

            mask_key = f"__CONTEXT_INSTRUMENT__:{match.matched_name[:50]}"
            mask_ranges.append((token_start, token_end, mask_key))

    return mask_ranges
