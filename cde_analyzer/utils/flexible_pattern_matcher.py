#
# File: utils/flexible_pattern_matcher.py
#
"""
Flexible pattern matching for verbatim phrase discovery.

Generates case-insensitive regex patterns with optional articles, pronouns,
and flexible whitespace to discover actual verbatim occurrences in text.

The discovered verbatim phrases can then be used for exact string substitution,
avoiding pattern matching overhead and ordering issues.
"""

import re
import logging
import multiprocessing as mp
from functools import partial
from typing import Set, List, Dict, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Anchor prefixes that should be matched literally (not made optional)
# These introduce instruments and must be preserved
ANCHOR_PREFIXES = [
    "as part of",
    "as a part of",
    "based on",
    "from",
    "field of",
    "a field of",
]

# Articles that can be optional (0 or 1 occurrence)
OPTIONAL_ARTICLES = {"the", "a", "an"}

# Pronouns/prepositions that can be optional when NOT in anchor
OPTIONAL_WORDS = {"to", "for", "in", "on", "with", "by", "at"}

# Words that should never be made optional
REQUIRED_WORDS = {"part", "based", "field"}

# Version-like keywords that precede version numbers
VERSION_KEYWORDS = {"version", "ver", "v"}

# Optional embedded abbreviation pattern for insertion between words
# Matches: nothing OR whitespace-(ABBREV)-whitespace OR whitespace-(ABBREV-N)-whitespace
EMBEDDED_ABBREV_OPTIONAL = r'(?:\s*\([A-Z]+(?:-\d+)?\)\s*)?'


def get_optimal_workers(n_workers: int = 0) -> int:
    """
    Calculate optimal worker count for parallel processing.

    Strategy:
    - n_workers > 0: Use specified value (user override)
    - n_workers == 0: Auto-detect with reserved headroom:
        - nCPU <= 10: use n-1 workers (leave 1 for system)
        - nCPU > 10: use n-2 workers (leave 2 for system/other users)
    - n_workers < 0: Sequential processing (return 1)

    Args:
        n_workers: Requested worker count (0=auto, negative=sequential)

    Returns:
        Optimal number of workers (minimum 1)
    """
    if n_workers > 0:
        return n_workers
    if n_workers < 0:
        return 1

    # Auto-detect
    cpu_count = mp.cpu_count() or 4  # Fallback if detection fails

    if cpu_count <= 10:
        # Leave 1 CPU for system activity
        return max(1, cpu_count - 1)
    else:
        # Leave 2 CPUs for system/other users on larger machines
        return max(1, cpu_count - 2)


def _escape_for_regex(word: str) -> str:
    """Escape special regex characters in a word."""
    return re.escape(word)


def _normalize_version_number(word: str) -> Tuple[str, bool]:
    """
    Convert version number to flexible regex that matches semantic equivalents.

    "2.0" → matches "2", "2.0", "2.00" (trailing zeros are semantically equivalent)
    "2.5" → matches "2.5" only (non-zero decimal has semantic meaning)
    "10"  → matches "10", "10.0", "10.00" (can have trailing zeros added)

    Args:
        word: Token that might be a version number

    Returns:
        Tuple of (regex_fragment, was_version_number)
    """
    # Check if word is a number (possibly with decimal)
    match = re.match(r'^(\d+)(?:\.(\d+))?$', word)
    if not match:
        return _escape_for_regex(word), False

    integer_part = match.group(1)
    decimal_part = match.group(2)

    if decimal_part:
        # Check if decimal is all zeros (semantically equivalent to integer)
        if all(c == '0' for c in decimal_part):
            # "2.0" or "2.00" → matches "2", "2.0", "2.00" etc
            return rf'{integer_part}(?:\.0+)?', True
        else:
            # "2.5" → exact match only (semantic value matters)
            return _escape_for_regex(f"{integer_part}.{decimal_part}"), True
    else:
        # "2" → matches "2", "2.0", "2.00" etc
        return rf'{integer_part}(?:\.0+)?', True


def _find_anchor_prefix(pattern: str) -> Tuple[Optional[str], str]:
    """
    Find and extract anchor prefix from pattern.

    Args:
        pattern: Original pattern string

    Returns:
        Tuple of (anchor_prefix, remainder) or (None, pattern)
    """
    pattern_lower = pattern.lower()

    # Sort by length descending to match longest first
    for anchor in sorted(ANCHOR_PREFIXES, key=len, reverse=True):
        if pattern_lower.startswith(anchor):
            # Check for word boundary (space or end)
            rest_start = len(anchor)
            if rest_start >= len(pattern) or pattern[rest_start].isspace():
                return pattern[:rest_start], pattern[rest_start:].lstrip()

    return None, pattern


def _make_anchor_regex(anchor: str) -> str:
    r"""
    Convert anchor prefix to regex with flexible whitespace.

    'as part of' → r'as\s+part\s+of'
    """
    words = anchor.split()
    escaped = [_escape_for_regex(w) for w in words]
    return r'\s+'.join(escaped)


def _make_flexible_word_regex(word: str, is_optional: bool = False, include_following_space: bool = False) -> str:
    """
    Convert a word to flexible regex.

    Args:
        word: The word to convert
        is_optional: If True, entire word is optional
        include_following_space: If True, include \\s+ in the optional group
                                 (used when the word is optional and followed by more words)

    Returns:
        Regex fragment for this word
    """
    escaped = _escape_for_regex(word)

    # Handle hyphenated words: "Neuro-QOL" → "Neuro[-\s]?QOL"
    if '-' in word:
        parts = word.split('-')
        escaped_parts = [_escape_for_regex(p) for p in parts]
        escaped = r'[-\s]?'.join(escaped_parts)

    if is_optional:
        if include_following_space:
            # Include the following space in the optional group
            # This way, if the word is absent, no space is required
            return f'(?:{escaped}\\s+)?'
        else:
            return f'(?:{escaped}\\s*)?'
    else:
        return escaped


def make_flexible_regex(
    pattern: str,
    allow_abbrev_variants: bool = False,
    allow_embedded_abbrev: bool = False,
) -> str:
    """
    Convert a pattern to a flexible case-insensitive regex.

    Rules:
    - Anchor prefixes ("as part of", "based on") are literal with flexible whitespace
    - Articles (the, a, an) are optional (0 or 1)
    - Whitespace is flexible (\\s+ or \\s*)
    - Hyphens can match hyphen, space, or nothing
    - Prepositions (to, for, in, etc.) are optional when not in anchor

    Enhanced rules (when enabled):
    - allow_abbrev_variants: (ABC) matches (ABC), (ABC-1), (ABC-2), etc.
    - allow_embedded_abbrev: Allows optional parenthetical abbreviations between words
      e.g., "Scale Long" can match "Scale (GDS) Long"

    Args:
        pattern: Original pattern string
        allow_abbrev_variants: If True, abbreviation parentheticals match variants
        allow_embedded_abbrev: If True, allow optional abbreviations between words

    Returns:
        Regex pattern string (compile with re.IGNORECASE)

    Examples:
        'as part of the Neuro-QOL' →
            r'as\\s+part\\s+of\\s+(?:the\\s+)?Neuro[-\\s]?QOL'

        'Risk Factor Questionnaire (RFQ)' →
            r'Risk\\s+Factor\\s+Questionnaire\\s*\\(RFQ\\)'

        'Patient Health Questionnaire (PHQ)' with allow_abbrev_variants=True →
            r'Patient\\s+Health\\s+Questionnaire\\s*\\(PHQ(?:-\\d+)?\\)'
    """
    if not pattern:
        return ''

    # Extract anchor prefix if present
    anchor, remainder = _find_anchor_prefix(pattern)

    regex_parts = []

    # Add anchor as literal (with flexible whitespace)
    if anchor:
        regex_parts.append(_make_anchor_regex(anchor))
        regex_parts.append(r'\s+')  # Space between anchor and remainder

    # Process remainder word by word
    if remainder:
        # Tokenize: split on whitespace but preserve structure
        # Also handle parentheses as separate tokens
        tokens = re.findall(r'\([^)]+\)|\S+', remainder)

        prev_was_optional = False
        prev_was_version_keyword = False

        for i, token in enumerate(tokens):
            token_lower = token.lower()

            # Handle parenthesized acronym: "(RFQ)" → r'\s*\(RFQ\)'
            if token.startswith('(') and token.endswith(')'):
                inner = token[1:-1]
                # Flexible space before paren, then literal paren content
                # Skip spacing if previous token was optional (already included)
                if i > 0 and not prev_was_optional:
                    regex_parts.append(r'\s*')

                # Enhanced: Check if this is an abbreviation-style parenthetical
                # Pattern: all caps, possibly followed by hyphen and digits (e.g., PHQ, PHQ-9)
                if allow_abbrev_variants and re.match(r'^[A-Z]+(?:-\d+)?$', inner):
                    # Extract base abbreviation (letters before any hyphen-number)
                    base_match = re.match(r'^([A-Z]+)', inner)
                    if base_match:
                        base_abbrev = base_match.group(1)
                        # Generate pattern that matches: (PHQ), (PHQ-9), (PHQ-15), etc.
                        regex_parts.append(rf'\({re.escape(base_abbrev)}(?:-\d+)?\)')
                    else:
                        regex_parts.append(r'\(' + _escape_for_regex(inner) + r'\)')
                else:
                    regex_parts.append(r'\(' + _escape_for_regex(inner) + r'\)')

                prev_was_optional = False
                prev_was_version_keyword = False
                continue

            # Add inter-word spacing (flexible)
            # Note: spacing after anchor is already added above, so only add
            # spacing between words in the remainder (i > 0)
            # Skip if previous token was optional (spacing is in the optional group)
            if i > 0 and not prev_was_optional:
                if allow_embedded_abbrev:
                    # Allow optional parenthetical abbreviation between words
                    # e.g., "Scale Long" can match "Scale (GDS) Long"
                    regex_parts.append(r'\s+' + EMBEDDED_ABBREV_OPTIONAL)
                else:
                    regex_parts.append(r'\s+')

            # Check if this is a version keyword
            if token_lower in VERSION_KEYWORDS:
                regex_parts.append(_escape_for_regex(token))
                prev_was_optional = False
                prev_was_version_keyword = True
                continue

            # Check if previous token was a version keyword and this looks like a number
            if prev_was_version_keyword:
                version_regex, is_version = _normalize_version_number(token)
                if is_version:
                    regex_parts.append(version_regex)
                    prev_was_optional = False
                    prev_was_version_keyword = False
                    continue

            # Determine if word should be optional
            is_optional = False
            if token_lower in OPTIONAL_ARTICLES:
                is_optional = True
            elif token_lower in OPTIONAL_WORDS and token_lower not in REQUIRED_WORDS:
                is_optional = True

            # Check if there are more tokens after this one
            has_following_tokens = i < len(tokens) - 1

            regex_parts.append(_make_flexible_word_regex(
                token, is_optional, include_following_space=(is_optional and has_following_tokens)
            ))
            prev_was_optional = is_optional
            prev_was_version_keyword = False

    # Add terminal boundary: match if followed by whitespace, punctuation, or end of string
    # This allows both infix matches (mid-sentence) and suffix matches (end of sentence)
    # Using lookahead with character class for common terminators
    regex_parts.append(r'(?=[\s.,;:!?"\'()\[\]]|$)')

    return ''.join(regex_parts)


def _strip_version_prefix(text: str) -> str:
    """
    Strip version prefix like "version 2.0 of" from start of text.

    "version 2.0 of 12-item SF" → "12-item SF"
    "Version 2 of the SF-12" → "the SF-12"
    "12-item SF" → "12-item SF" (unchanged)

    Args:
        text: Text that may start with version prefix

    Returns:
        Text with version prefix removed
    """
    # Pattern: (version|ver|v) followed by number, optionally followed by "of"
    version_pattern = re.compile(
        r'^(?:version|ver|v)\s+\d+(?:\.\d+)?\s+(?:of\s+)?',
        re.IGNORECASE
    )
    return version_pattern.sub('', text).strip()


def generate_prefixed_patterns(bare_names: List[str]) -> List[Tuple[str, str]]:
    """
    Generate anchor-prefixed patterns from bare instrument names.

    For each bare name, generates patterns with all known anchor prefixes.
    This allows discovering instrument mentions like "as part of PHQ-9" or "based on PHQ-9"
    when the input list contains only bare names like "PHQ-9".

    Args:
        bare_names: List of bare instrument names (without anchor prefixes)

    Returns:
        List of (prefixed_pattern, bare_name) tuples
    """
    results = []
    seen = set()

    for bare_name in bare_names:
        bare_name = bare_name.strip()
        if not bare_name:
            continue

        # Check if this bare name already has an anchor (skip if so)
        anchor, _ = _find_anchor_prefix(bare_name)
        if anchor:
            continue

        for anchor in ANCHOR_PREFIXES:
            prefixed = f"{anchor} {bare_name}"
            if prefixed not in seen:
                results.append((prefixed, bare_name))
                seen.add(prefixed)

    logger.info(f"Generated {len(results)} prefixed patterns from {len(bare_names)} bare names")
    return results


def extract_bare_instrument_name(pattern: str) -> Optional[str]:
    """
    Extract the instrument name from a pattern by removing anchor and version prefixes.

    "as part of the Neuro-QOL Test" → "Neuro-QOL Test"
    "as part of version 2.0 of 12-item SF" → "12-item SF"
    "based on PHQ-9" → "PHQ-9"
    "PHQ-9" → None (no anchor prefix found)

    Args:
        pattern: Original pattern string

    Returns:
        The bare instrument name if anchor was found, None otherwise
    """
    anchor, remainder = _find_anchor_prefix(pattern)
    if anchor and remainder:
        # Strip version prefix like "version 2.0 of"
        remainder = _strip_version_prefix(remainder)

        # Also strip optional articles from the beginning
        remainder = remainder.strip()
        words = remainder.split(None, 1)
        if words and words[0].lower() in OPTIONAL_ARTICLES:
            if len(words) > 1:
                return words[1].strip()
            else:
                return None  # Only article, no actual name
        return remainder
    return None


def extract_bare_instrument_names(
    patterns: List[str],
    min_words: int = 0
) -> List[Tuple[str, str]]:
    """
    Extract bare instrument names from a list of patterns.

    Args:
        patterns: List of pattern strings (e.g., from instrument list)
        min_words: Minimum word count for bare names (0 = no filter).
                   Filters short fragments like "Score" that cause false positives.

    Returns:
        List of (original_pattern, bare_name) tuples for patterns that had anchors
    """
    results = []
    seen_names = set()
    filtered_count = 0

    for pattern in patterns:
        bare_name = extract_bare_instrument_name(pattern)
        if bare_name and bare_name not in seen_names:
            if min_words > 0 and len(bare_name.split()) < min_words:
                filtered_count += 1
                continue
            results.append((pattern, bare_name))
            seen_names.add(bare_name)

    if filtered_count:
        logger.info(f"Filtered {filtered_count} bare names with < {min_words} words")
    logger.info(f"Extracted {len(results)} unique bare instrument names from {len(patterns)} patterns")
    return results


def extract_core_instrument_name(bare_name: str) -> Tuple[str, Optional[str]]:
    """
    Extract core instrument name (before acronym) and the acronym separately.

    "12-item Short Form Health Survey (SF-12)" → ("12-item Short Form Health Survey", "SF-12")
    "PHQ-9" → ("PHQ-9", None)
    "Neuro-QOL Test (NQT)" → ("Neuro-QOL Test", "NQT")

    Args:
        bare_name: Bare instrument name (without anchor prefix)

    Returns:
        Tuple of (core_name, acronym) where acronym may be None
    """
    # Check for trailing parenthesized acronym
    match = re.match(r'^(.+?)\s*\(([^)]+)\)$', bare_name)
    if match:
        core = match.group(1).strip()
        acronym = match.group(2)
        return core, acronym
    return bare_name, None


def make_core_name_regex(bare_name: str) -> str:
    """
    Generate regex that matches an instrument's core name with optional version and acronym.

    For "12-item Short Form Health Survey (SF-12)", generates regex matching:
    - "12-item Short Form Health Survey" (core only)
    - "12-item Short Form Health Survey (SF-12)" (with original acronym)
    - "12-item Short Form Health Survey Version 2 (SF-12v2)" (with version and variant acronym)
    - "12-item Short Form Health Survey v2.0" (with compact version)

    Args:
        bare_name: Bare instrument name (without anchor prefix)

    Returns:
        Regex pattern string (compile with re.IGNORECASE)
    """
    core, acronym = extract_core_instrument_name(bare_name)

    # Build regex for core name using flexible matching
    # (handles hyphens, articles, etc.)
    tokens = re.findall(r'\S+', core)
    core_parts = []

    for i, token in enumerate(tokens):
        if i > 0:
            core_parts.append(r'\s+')

        token_lower = token.lower()

        # Handle optional articles
        if token_lower in OPTIONAL_ARTICLES:
            core_parts.append(f'(?:{_escape_for_regex(token)}\\s+)?')
            continue

        # Handle hyphenated words
        if '-' in token:
            parts = token.split('-')
            escaped_parts = [_escape_for_regex(p) for p in parts]
            core_parts.append(r'[-\s]?'.join(escaped_parts))
        else:
            core_parts.append(_escape_for_regex(token))

    core_regex = ''.join(core_parts)

    # Add optional version suffix: "Version 2", "v2.0", "Ver 2", etc.
    version_suffix = r'(?:\s+(?:version|ver|v)\.?\s*\d+(?:\.\d+)?)?'

    # Add optional acronym suffix: "(SF-12)", "(SF-12v2)", etc.
    # Match any parenthesized content that starts with similar letters
    if acronym:
        # Extract base acronym (letters before any numbers)
        acronym_base_match = re.match(r'^([A-Za-z]+)', acronym)
        if acronym_base_match:
            base = acronym_base_match.group(1)
            # Match acronym variations: (SF-12), (SF-12v2), (SF12), etc.
            acronym_suffix = rf'(?:\s*\({re.escape(base)}[-\s]?[^\)]*\))?'
        else:
            acronym_suffix = rf'(?:\s*\([^\)]+\))?'
    else:
        # Allow any optional parenthesized acronym
        acronym_suffix = r'(?:\s*\([^\)]+\))?'

    # Add terminal boundary for infix/suffix matching
    terminal_boundary = r'(?=[\s.,;:!?"\'()\[\]]|$)'

    return core_regex + version_suffix + acronym_suffix + terminal_boundary


def compile_flexible_patterns(
    patterns: List[str],
    allow_abbrev_variants: bool = False,
    allow_embedded_abbrev: bool = False,
) -> List[Tuple[str, re.Pattern]]:
    """
    Compile a list of patterns into flexible regex patterns.

    Args:
        patterns: List of pattern strings
        allow_abbrev_variants: If True, abbreviation parentheticals match variants
            e.g., (PHQ) will also match (PHQ-9), (PHQ-15), etc.
        allow_embedded_abbrev: If True, allow optional abbreviations between words
            e.g., "Scale Long" can match "Scale (GDS) Long"

    Returns:
        List of (original_pattern, compiled_regex) tuples
    """
    compiled = []

    for pattern in patterns:
        try:
            regex_str = make_flexible_regex(
                pattern,
                allow_abbrev_variants=allow_abbrev_variants,
                allow_embedded_abbrev=allow_embedded_abbrev,
            )
            if regex_str:
                compiled_re = re.compile(regex_str, re.IGNORECASE)
                compiled.append((pattern, compiled_re))
        except re.error as e:
            logger.warning(f"Failed to compile regex for pattern '{pattern}': {e}")

    logger.info(f"Compiled {len(compiled)} flexible patterns from {len(patterns)} inputs")
    return compiled


def _discover_texts_chunk_worker(
    chunk_data: Tuple[int, List[Tuple[str, str, str]]],
    pattern_strings: List[Tuple[str, str]]
) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """
    Worker function for parallel discovery over text chunks.

    Args:
        chunk_data: Tuple of (chunk_index, list of (tinyId, field_path, text) tuples)
        pattern_strings: List of (original_pattern, regex_string) tuples

    Returns:
        Tuple of (verbatim_to_tinyids dict, set of matched patterns)
    """
    chunk_idx, texts_chunk = chunk_data
    verbatim_to_tinyids: Dict[str, Set[str]] = defaultdict(set)
    matched_patterns: Set[str] = set()

    # Compile patterns in this worker (regex objects can't be pickled)
    compiled = []
    for original, regex_str in pattern_strings:
        try:
            compiled.append((original, re.compile(regex_str, re.IGNORECASE)))
        except re.error:
            pass  # Skip invalid patterns

    for tiny_id, field_path, text in texts_chunk:
        if not text:
            continue
        for original_pattern, regex in compiled:
            for match in regex.finditer(text):
                verbatim = match.group(0)
                verbatim_to_tinyids[verbatim].add(tiny_id)
                matched_patterns.add(original_pattern)

    return dict(verbatim_to_tinyids), matched_patterns


def _discover_patterns_chunk_worker(
    chunk_data: Tuple[int, List[Tuple[str, str]]],
    texts_with_ids: List[Tuple[str, str, str]]
) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """
    Worker function for parallel discovery over pattern chunks.

    Args:
        chunk_data: Tuple of (chunk_index, list of (original_pattern, regex_string) tuples)
        texts_with_ids: List of (tinyId, field_path, text) tuples

    Returns:
        Tuple of (verbatim_to_tinyids dict, set of matched patterns)
    """
    chunk_idx, patterns_chunk = chunk_data
    verbatim_to_tinyids: Dict[str, Set[str]] = defaultdict(set)
    matched_patterns: Set[str] = set()

    # Compile patterns in this worker
    compiled = []
    for original, regex_str in patterns_chunk:
        try:
            compiled.append((original, re.compile(regex_str, re.IGNORECASE)))
        except re.error:
            pass

    for tiny_id, field_path, text in texts_with_ids:
        if not text:
            continue
        for original_pattern, regex in compiled:
            for match in regex.finditer(text):
                verbatim = match.group(0)
                verbatim_to_tinyids[verbatim].add(tiny_id)
                matched_patterns.add(original_pattern)

    return dict(verbatim_to_tinyids), matched_patterns


def _merge_verbatim_results(
    results: List[Tuple[Dict[str, Set[str]], Set[str]]]
) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """Merge results from parallel workers."""
    merged_verbatim: Dict[str, Set[str]] = defaultdict(set)
    merged_matched: Set[str] = set()

    for verbatim_dict, matched_set in results:
        for verbatim, tinyids in verbatim_dict.items():
            merged_verbatim[verbatim].update(tinyids)
        merged_matched.update(matched_set)

    return dict(merged_verbatim), merged_matched


def discover_verbatim_occurrences(
    texts_with_ids: List[Tuple[str, str, str]],
    compiled_patterns: List[Tuple[str, re.Pattern]],
    progress_callback: Optional[callable] = None,
    pattern_to_expected_tinyids: Optional[Dict[str, Set[str]]] = None,
    n_workers: int = 1
) -> Tuple[Dict[str, Set[str]], List[Tuple[str, str, Set[str]]]]:
    """
    Discover actual verbatim occurrences of patterns in text.

    Args:
        texts_with_ids: List of (tinyId, field_path, text) tuples
        compiled_patterns: List of (original_pattern, compiled_regex) tuples
        progress_callback: Optional callback(current, total) for progress
        pattern_to_expected_tinyids: Optional dict mapping original_pattern → set of
            expected tinyIds. When provided, each pattern is only searched in texts
            from its expected tinyIds (efficiency optimization).
        n_workers: Number of parallel workers (0=auto-detect CPU count, 1=sequential).
            When >1, auto-detects optimal parallelization dimension:
            - If texts > patterns: parallelize over texts
            - If patterns > texts: parallelize over patterns

    Returns:
        Tuple of:
        - Dict mapping verbatim_phrase → set of tinyIds where it occurs
        - List of failed patterns: (original_pattern, regex_str, expected_tinyIds)
    """
    # Resolve worker count using optimal calculation
    n_workers = get_optimal_workers(n_workers)

    n_texts = len(texts_with_ids)
    n_patterns = len(compiled_patterns)

    # Use parallel processing if workers > 1 and we're in full scan mode (no tinyId filtering)
    if n_workers > 1 and not pattern_to_expected_tinyids and n_texts > 100 and n_patterns > 100:
        # Extract pattern strings for pickling (regex objects can't be pickled)
        pattern_strings = [(orig, regex.pattern) for orig, regex in compiled_patterns]

        # Auto-detect: parallelize over the larger dimension
        if n_texts >= n_patterns:
            # Parallelize over texts
            logger.info(f"Parallel discovery: {n_workers} workers over {n_texts} texts (vs {n_patterns} patterns)")
            chunk_size = max(1, n_texts // n_workers)
            chunks = [
                (i, texts_with_ids[i * chunk_size:(i + 1) * chunk_size])
                for i in range(n_workers)
            ]
            # Handle remainder
            if n_texts % n_workers > 0:
                chunks[-1] = (chunks[-1][0], texts_with_ids[(n_workers - 1) * chunk_size:])

            worker_func = partial(_discover_texts_chunk_worker, pattern_strings=pattern_strings)
        else:
            # Parallelize over patterns
            logger.info(f"Parallel discovery: {n_workers} workers over {n_patterns} patterns (vs {n_texts} texts)")
            chunk_size = max(1, n_patterns // n_workers)
            chunks = [
                (i, pattern_strings[i * chunk_size:(i + 1) * chunk_size])
                for i in range(n_workers)
            ]
            # Handle remainder
            if n_patterns % n_workers > 0:
                chunks[-1] = (chunks[-1][0], pattern_strings[(n_workers - 1) * chunk_size:])

            worker_func = partial(_discover_patterns_chunk_worker, texts_with_ids=texts_with_ids)

        # Execute in parallel with graceful interrupt handling
        try:
            with mp.Pool(processes=n_workers) as pool:
                results = pool.map(worker_func, chunks)
        except KeyboardInterrupt:
            logger.warning("Interrupted - terminating worker pool...")
            pool.terminate()
            pool.join()
            raise  # Re-raise to let parent handle gracefully

        # Merge results
        verbatim_to_tinyids, matched_patterns = _merge_verbatim_results(results)

        # Build failed patterns list
        failed_patterns = []
        for original_pattern, regex in compiled_patterns:
            if original_pattern not in matched_patterns:
                failed_patterns.append((original_pattern, regex.pattern, set()))

        logger.info(f"Discovered {len(verbatim_to_tinyids)} unique verbatim phrases (parallel)")
        if failed_patterns:
            logger.warning(f"Failed to match {len(failed_patterns)} patterns")

        return verbatim_to_tinyids, failed_patterns

    # Sequential processing (original logic)
    verbatim_to_tinyids: Dict[str, Set[str]] = defaultdict(set)
    pattern_matched: Dict[str, bool] = {}  # Track which patterns found matches

    # Build tinyId → texts index if using filtered discovery
    tinyid_to_texts: Optional[Dict[str, List[Tuple[str, str]]]] = None
    if pattern_to_expected_tinyids:
        tinyid_to_texts = defaultdict(list)
        for tiny_id, field_path, text in texts_with_ids:
            if text:
                tinyid_to_texts[tiny_id].append((field_path, text))
        logger.info(f"Built tinyId index with {len(tinyid_to_texts)} unique tinyIds")

    if pattern_to_expected_tinyids and tinyid_to_texts:
        # Filtered discovery: search each pattern only in expected tinyIds
        total = len(compiled_patterns)
        for i, (original_pattern, regex) in enumerate(compiled_patterns):
            expected_ids = pattern_to_expected_tinyids.get(original_pattern, set())
            pattern_matched[original_pattern] = False

            for tiny_id in expected_ids:
                if tiny_id not in tinyid_to_texts:
                    continue
                for field_path, text in tinyid_to_texts[tiny_id]:
                    for match in regex.finditer(text):
                        verbatim = match.group(0)
                        verbatim_to_tinyids[verbatim].add(tiny_id)
                        pattern_matched[original_pattern] = True

            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, total)
    else:
        # Full scan: search all patterns in all texts
        total = len(texts_with_ids)
        for original_pattern, _ in compiled_patterns:
            pattern_matched[original_pattern] = False

        for i, (tiny_id, field_path, text) in enumerate(texts_with_ids):
            if not text:
                continue

            for original_pattern, regex in compiled_patterns:
                for match in regex.finditer(text):
                    verbatim = match.group(0)
                    verbatim_to_tinyids[verbatim].add(tiny_id)
                    pattern_matched[original_pattern] = True

            if progress_callback and (i + 1) % 1000 == 0:
                progress_callback(i + 1, total)

    # Collect failed patterns
    failed_patterns = []
    for original_pattern, regex in compiled_patterns:
        if not pattern_matched.get(original_pattern, False):
            expected_ids = pattern_to_expected_tinyids.get(original_pattern, set()) if pattern_to_expected_tinyids else set()
            failed_patterns.append((original_pattern, regex.pattern, expected_ids))

    logger.info(f"Discovered {len(verbatim_to_tinyids)} unique verbatim phrases")
    if failed_patterns:
        logger.warning(f"Failed to match {len(failed_patterns)} patterns")

    return dict(verbatim_to_tinyids), failed_patterns


def write_failed_patterns_tsv(
    failed_patterns: List[Tuple[str, str, Set[str]]],
    output_path: str
) -> None:
    """
    Write failed patterns to TSV file for diagnosis.

    Format: original_pattern<TAB>regex<TAB>expected_tinyIds

    Args:
        failed_patterns: List of (original_pattern, regex_str, expected_tinyIds) tuples
        output_path: Path to output TSV file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("original_pattern\tregex\texpected_tinyIds\n")
        for pattern, regex_str, expected_ids in failed_patterns:
            ids_str = ' '.join(sorted(expected_ids)) if expected_ids else ''
            f.write(f"{pattern}\t{regex_str}\t{ids_str}\n")

    logger.info(f"Wrote {len(failed_patterns)} failed patterns to {output_path}")


def write_verbatim_tsv(
    verbatim_map: Dict[str, Set[str]],
    output_path: str,
    sort_by_length: bool = True
) -> None:
    """
    Write discovered verbatim phrases to TSV file.

    Format: verbatim<TAB>tinyId1 tinyId2 tinyId3...

    Args:
        verbatim_map: Dict mapping verbatim_phrase → set of tinyIds
        output_path: Path to output TSV file
        sort_by_length: If True, sort by phrase length descending (for longest-first processing)
    """
    items = list(verbatim_map.items())

    if sort_by_length:
        items.sort(key=lambda x: len(x[0]), reverse=True)
    else:
        items.sort(key=lambda x: x[0])  # Alphabetical

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("verbatim\ttinyIds\n")
        for verbatim, tinyids in items:
            tinyids_str = ' '.join(sorted(tinyids))
            f.write(f"{verbatim}\t{tinyids_str}\n")

    logger.info(f"Wrote {len(items)} verbatim patterns to {output_path}")


def load_verbatim_tsv(
    input_path: str
) -> List[Tuple[str, Set[str]]]:
    """
    Load verbatim phrases from TSV file.

    Args:
        input_path: Path to TSV file

    Returns:
        List of (verbatim_phrase, set_of_tinyIds) tuples in file order
    """
    results = []

    with open(input_path, 'r', encoding='utf-8') as f:
        header = f.readline()  # Skip header

        for line in f:
            line = line.rstrip('\n\r')
            if not line:
                continue

            parts = line.split('\t', 1)
            if len(parts) < 2:
                continue

            verbatim = parts[0]
            # Support both space-separated and pipe-separated formats (or mixed)
            tinyids = set(t for t in re.split(r'[\s|]+', parts[1]) if t) if parts[1] else set()
            results.append((verbatim, tinyids))

    logger.info(f"Loaded {len(results)} verbatim patterns from {input_path}")
    return results


def merge_verbatim_tsv(
    input_path: str,
    output_path: str,
    pattern_column: str = "full_match",
    tinyids_column: str = "tinyIds",
    sort_by_length: bool = True
) -> Dict[str, int]:
    """
    Merge rows with identical patterns, combining their tinyId sets.

    This is used after curation where edited patterns may become identical.
    The merge combines tinyId sets and outputs deduplicated rows.

    Args:
        input_path: Path to input TSV file
        output_path: Path to output TSV file
        pattern_column: Column name for patterns (default: 'full_match')
        tinyids_column: Column name for tinyIds (default: 'tinyIds')
        sort_by_length: If True, sort output by pattern length descending

    Returns:
        Dict with merge statistics:
        - 'input_rows': Number of input rows
        - 'output_rows': Number of output rows (after merge)
        - 'merged_count': Number of patterns that had duplicates merged
    """
    # Read input and merge by pattern
    pattern_to_tinyids: Dict[str, Set[str]] = {}
    input_rows = 0

    with open(input_path, 'r', encoding='utf-8') as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        try:
            pattern_idx = headers.index(pattern_column)
        except ValueError:
            raise ValueError(
                f"Pattern column '{pattern_column}' not found in {input_path}. "
                f"Available columns: {', '.join(headers)}"
            )

        tinyids_idx = None
        if tinyids_column in headers:
            tinyids_idx = headers.index(tinyids_column)

        for line in f:
            line = line.rstrip('\n\r')
            if not line:
                continue

            input_rows += 1
            fields = line.split('\t')

            if pattern_idx >= len(fields):
                continue

            # Strip Excel's auto-added quotes around fields containing commas
            pattern = fields[pattern_idx].strip().strip('"')
            if not pattern:
                continue

            # Parse tinyIds
            # Support both space-separated and pipe-separated formats (or mixed)
            tinyids = set()
            if tinyids_idx is not None and tinyids_idx < len(fields):
                tinyids_str = fields[tinyids_idx].strip().strip('"')
                if tinyids_str:
                    tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)

            # Merge into existing set or create new entry
            if pattern in pattern_to_tinyids:
                pattern_to_tinyids[pattern].update(tinyids)
            else:
                pattern_to_tinyids[pattern] = tinyids

    # Count patterns that had duplicates merged
    # (This requires tracking occurrence counts during merge)
    # For simplicity, we just report the reduction
    merged_count = input_rows - len(pattern_to_tinyids)

    # Sort and write output
    items = list(pattern_to_tinyids.items())
    if sort_by_length:
        items.sort(key=lambda x: len(x[0]), reverse=True)
    else:
        items.sort(key=lambda x: x[0])  # Alphabetical

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"{pattern_column}\t{tinyids_column}\n")
        for pattern, tinyids in items:
            tinyids_str = ' '.join(sorted(tinyids))
            f.write(f"{pattern}\t{tinyids_str}\n")

    stats = {
        'input_rows': input_rows,
        'output_rows': len(pattern_to_tinyids),
        'merged_count': merged_count
    }

    logger.info(
        f"Merged {input_path}: {input_rows} rows → {len(pattern_to_tinyids)} unique patterns "
        f"({merged_count} duplicates merged)"
    )

    return stats


def merge_verbatim_cli(
    input_path: str,
    output_path: Optional[str] = None,
    pattern_column: str = "full_match",
    tinyids_column: str = "tinyIds"
) -> None:
    """
    CLI wrapper for merge_verbatim_tsv.

    If output_path is not specified, appends '_merged' before extension.
    """
    from pathlib import Path

    if output_path is None:
        p = Path(input_path)
        output_path = str(p.with_stem(p.stem + '_merged'))

    stats = merge_verbatim_tsv(
        input_path,
        output_path,
        pattern_column=pattern_column,
        tinyids_column=tinyids_column
    )

    print(f"Input:  {stats['input_rows']} rows")
    print(f"Output: {stats['output_rows']} unique patterns")
    print(f"Merged: {stats['merged_count']} duplicate patterns")
    print(f"Wrote:  {output_path}")


def coalesce_variants_tsv(
    input_path: str,
    output_path: str,
    pattern_column: str = "pattern",
    tinyids_column: str = "tinyIds",
    report_path: Optional[str] = None,
    min_prefix_tinyids: int = 0,
    min_parent_tinyids: int = 0,
    rollup_subset_tinyids: bool = False,
    trim_anchors: bool = True,
    emit_def_variants: bool = False
) -> Dict[str, int]:
    """
    Coalesce pattern variants by removing shorter patterns subsumed by longer ones.

    A shorter pattern is subsumed if:
    1. It is a substring of one or more longer patterns
    2. Its tinyIds are a subset of the union of those longer patterns' tinyIds

    This eliminates redundant variants like:
    - "in the past 7 days" (tinyIds: A B C)
    - "in the past 7 days:" (tinyIds: A B)
    - "in the past 7 days - " (tinyIds: C)

    Since tinyIds {A,B,C} ⊆ {A,B} ∪ {C}, the base pattern is subsumed.

    When min_prefix_tinyids > 0, also extracts common prefix patterns:
    - Groups patterns by their word-level common prefixes
    - Finds longest prefixes meeting the min_prefix_tinyids threshold
    - Replaces groups of patterns with their common prefix pattern
    - Example: "as part of Neuro-QOL Lower..." and "as part of Neuro-QOL Upper..."
      become "as part of Neuro-QOL" if that prefix covers enough tinyIds

    Args:
        input_path: Path to input TSV file
        output_path: Path to output TSV file (coalesced patterns)
        pattern_column: Column name for patterns (default: 'pattern')
        tinyids_column: Column name for tinyIds (default: 'tinyIds')
        report_path: Optional path to write subsumption report TSV
        min_prefix_tinyids: Minimum tinyIds for prefix extraction (0 = disabled)
        min_parent_tinyids: Minimum parent tinyId count threshold (0 = disabled).
            When > 0, patterns whose parent_tinyid_count < threshold are dropped.
            Requires parent_phrase and parent_tinyid_count columns in input.

    Returns:
        Dict with coalesce statistics:
        - 'input_patterns': Number of input patterns
        - 'output_patterns': Number of output patterns (after coalesce)
        - 'subsumed_count': Number of patterns removed by subsumption
        - 'prefix_extracted_count': Number of patterns replaced by prefixes
        - 'subsumptions': List of (subsumed_pattern, covering_patterns) tuples
    """
    # Load all patterns with tinyIds and optional parent info
    pattern_to_tinyids: Dict[str, Set[str]] = {}
    pattern_to_parent: Dict[str, str] = {}
    pattern_to_parent_count: Dict[str, int] = {}
    has_parent_columns = False

    with open(input_path, 'r', encoding='utf-8') as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        try:
            pattern_idx = headers.index(pattern_column)
        except ValueError:
            raise ValueError(
                f"Pattern column '{pattern_column}' not found in {input_path}. "
                f"Available columns: {', '.join(headers)}"
            )

        tinyids_idx = None
        if tinyids_column in headers:
            tinyids_idx = headers.index(tinyids_column)

        # Detect parent columns
        parent_idx = None
        parent_count_idx = None
        if 'parent_phrase' in headers:
            parent_idx = headers.index('parent_phrase')
            has_parent_columns = True
        if 'parent_tinyid_count' in headers:
            parent_count_idx = headers.index('parent_tinyid_count')

        for line in f:
            line = line.rstrip('\n\r')
            if not line:
                continue

            fields = line.split('\t')
            if pattern_idx >= len(fields):
                continue

            pattern = fields[pattern_idx].strip().strip('"')
            if not pattern:
                continue

            # Parse tinyIds
            tinyids = set()
            if tinyids_idx is not None and tinyids_idx < len(fields):
                tinyids_str = fields[tinyids_idx].strip().strip('"')
                if tinyids_str:
                    tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)

            # Parse parent info
            if parent_idx is not None and parent_idx < len(fields):
                parent_val = fields[parent_idx].strip().strip('"')
                if parent_val:
                    pattern_to_parent[pattern] = parent_val
            if parent_count_idx is not None and parent_count_idx < len(fields):
                count_val = fields[parent_count_idx].strip()
                if count_val:
                    try:
                        pattern_to_parent_count[pattern] = int(count_val)
                    except ValueError:
                        pass

            # Merge tinyIds if pattern already exists
            if pattern in pattern_to_tinyids:
                pattern_to_tinyids[pattern].update(tinyids)
            else:
                pattern_to_tinyids[pattern] = tinyids

    input_patterns = len(pattern_to_tinyids)

    # Apply parent tinyId threshold filter
    parent_filtered_count = 0
    if min_parent_tinyids > 0 and has_parent_columns:
        patterns_to_remove = []
        for pattern in pattern_to_tinyids:
            parent_count = pattern_to_parent_count.get(pattern, 0)
            if parent_count < min_parent_tinyids:
                patterns_to_remove.append(pattern)
        for pattern in patterns_to_remove:
            del pattern_to_tinyids[pattern]
            parent_filtered_count += 1
        if parent_filtered_count:
            logger.info(
                f"Parent threshold filter: removed {parent_filtered_count} patterns "
                f"with parent_tinyid_count < {min_parent_tinyids}"
            )
    logger.info(f"Loaded {input_patterns} unique patterns from {input_path}")

    # Phase 0: Anchor trimming (default on)
    # Patterns containing anchor phrases ("as part of", "based on", etc.) are
    # trimmed to the bare instrument name. Content preceding the anchor is
    # CDE-specific text, not part of the instrument name. Discovery is intended
    # to find patterns without anchors.
    anchor_trimmed_count = 0
    anchor_trimmed_map: Dict[str, str] = {}  # original -> bare_name

    if trim_anchors:
        # Build regex to find anchors anywhere in pattern (case-insensitive)
        anchor_re = re.compile(
            r'(?:^|.*?\b)(' +
            '|'.join(re.escape(a) for a in sorted(ANCHOR_PREFIXES, key=len, reverse=True)) +
            r')\s+',
            re.IGNORECASE
        )

        patterns_to_trim = list(pattern_to_tinyids.keys())
        for pattern in patterns_to_trim:
            # First try prefix-only extraction (handles "as part of the X")
            bare_name = extract_bare_instrument_name(pattern)
            if not bare_name or bare_name == pattern:
                # Try mid-pattern anchor: "content, as part of the X"
                m = anchor_re.search(pattern)
                if m:
                    remainder = pattern[m.end():].strip()
                    if remainder:
                        # Strip optional leading article
                        words = remainder.split(None, 1)
                        if words and words[0].lower() in OPTIONAL_ARTICLES and len(words) > 1:
                            bare_name = words[1].strip()
                        else:
                            bare_name = remainder

            if bare_name and bare_name != pattern:
                tinyids = pattern_to_tinyids.pop(pattern)
                anchor_trimmed_map[pattern] = bare_name
                anchor_trimmed_count += 1

                # Merge tinyIds if bare name already exists
                if bare_name in pattern_to_tinyids:
                    pattern_to_tinyids[bare_name].update(tinyids)
                else:
                    pattern_to_tinyids[bare_name] = tinyids

                # Propagate parent info
                if pattern in pattern_to_parent and bare_name not in pattern_to_parent:
                    pattern_to_parent[bare_name] = pattern_to_parent[pattern]
                    if pattern in pattern_to_parent_count:
                        pattern_to_parent_count[bare_name] = pattern_to_parent_count[pattern]

        if anchor_trimmed_count:
            logger.info(
                f"Anchor trimming: {anchor_trimmed_count} patterns trimmed to bare names "
                f"({len(pattern_to_tinyids)} unique patterns remain)"
            )

    # Sort by length descending (longest first)
    sorted_patterns = sorted(pattern_to_tinyids.keys(), key=len, reverse=True)

    # Track which patterns are subsumed and by what
    subsumed: Dict[str, List[str]] = {}  # subsumed_pattern -> list of covering patterns
    kept_patterns: Set[str] = set()

    # Process from longest to shortest
    for pattern in sorted_patterns:
        pattern_tinyids = pattern_to_tinyids[pattern]

        # Check if this pattern is subsumed by any longer patterns we've kept
        covering_patterns = []
        covering_tinyids: Set[str] = set()

        for longer in kept_patterns:
            if pattern in longer:  # pattern is substring of longer
                covering_patterns.append(longer)
                covering_tinyids.update(pattern_to_tinyids[longer])

        # If pattern's tinyIds are covered by the union of covering patterns' tinyIds
        if covering_patterns and pattern_tinyids <= covering_tinyids:
            subsumed[pattern] = covering_patterns
            logger.debug(
                f"Subsumed: '{pattern[:50]}...' ({len(pattern_tinyids)} tinyIds) "
                f"covered by {len(covering_patterns)} longer patterns"
            )
        else:
            kept_patterns.add(pattern)

    # Phase 1b: Reverse subsumption (roll-down)
    # Removes LONG patterns that are greedy expansions of shorter base patterns.
    # If a shorter pattern is a text substring of a longer one AND the longer
    # pattern's tinyIds ⊆ shorter pattern's tinyIds, the long one is noise from
    # expansion gobbling adjacent text. Remove it.
    reverse_subsumed: Dict[str, str] = {}  # long_pattern -> shorter_base

    if rollup_subset_tinyids and kept_patterns:
        logger.info("Phase 1b: Reverse subsumption (roll-down greedy expansions)...")
        # Process longest first so we can remove them
        sorted_desc = sorted(kept_patterns, key=len, reverse=True)

        for long_pattern in sorted_desc:
            if long_pattern not in kept_patterns:
                continue
            long_tinyids = pattern_to_tinyids[long_pattern]

            # Find any shorter kept pattern that is a substring of this long pattern
            # and whose tinyIds fully cover the long pattern's tinyIds
            best_base = None
            for shorter in kept_patterns:
                if shorter == long_pattern:
                    continue
                if len(shorter) >= len(long_pattern):
                    continue
                if shorter in long_pattern and long_tinyids <= pattern_to_tinyids[shorter]:
                    # Skip single-word bases — generic words like "Scale" or "Score"
                    # shouldn't roll down specific multi-word instrument patterns
                    if len(shorter.split()) < 2:
                        continue
                    # Skip if long pattern contains a parenthesized abbreviation
                    # that the shorter base doesn't contain — the (ABBREV) suffix
                    # is structurally important for designation-level stripping
                    import re as _re
                    paren_match = _re.search(r'\([A-Z][A-Za-z0-9-]+\)', long_pattern)
                    if paren_match and paren_match.group() not in shorter:
                        continue
                    # Prefer the longest shorter base (most specific)
                    if best_base is None or len(shorter) > len(best_base):
                        best_base = shorter

            if best_base:
                reverse_subsumed[long_pattern] = best_base
                logger.debug(
                    f"Roll-down: '{long_pattern[:60]}' ({len(long_tinyids)} tinyIds) "
                    f"→ '{best_base[:60]}' ({len(pattern_to_tinyids[best_base])} tinyIds)"
                )

        # Remove rolled-down patterns
        for pattern in reverse_subsumed:
            kept_patterns.discard(pattern)

        if reverse_subsumed:
            logger.info(f"Reverse subsumption: removed {len(reverse_subsumed)} greedy expansions")

    # Phase 1.5: TinyId-subset rollup (if enabled)
    # Removes short patterns whose tinyIds are a strict subset of a longer pattern's tinyIds,
    # but ONLY when the short pattern is a text substring of the covering pattern.
    # This prevents rolling up variant names (e.g., "Name (ABBREV) -" vs "Name Scale (ABBREV) -").
    rollup_count = 0
    rollup_map: Dict[str, str] = {}  # rolled_up_pattern -> covering_pattern

    if rollup_subset_tinyids and kept_patterns:
        logger.info("Phase 1.5: TinyId-subset rollup for short patterns...")
        # Sort kept patterns by word count ascending (process shortest first)
        sorted_by_words = sorted(kept_patterns, key=lambda p: len(p.split()))

        for pattern in sorted_by_words:
            pattern_tinyids = pattern_to_tinyids[pattern]
            pattern_words = len(pattern.split())

            # Skip if already removed or if pattern has many tinyIds (likely legitimate)
            if pattern not in kept_patterns:
                continue

            # Find any single longer pattern that fully covers this pattern's tinyIds
            # AND contains this pattern as a text substring
            best_cover = None
            best_cover_len = 0

            for candidate in kept_patterns:
                if candidate == pattern:
                    continue
                candidate_words = len(candidate.split())
                # Covering pattern must be strictly longer (by word count)
                if candidate_words <= pattern_words:
                    continue
                # Short pattern must be a text substring of covering pattern
                if pattern not in candidate:
                    continue
                candidate_tinyids = pattern_to_tinyids[candidate]
                if pattern_tinyids <= candidate_tinyids:  # strict subset
                    if candidate_words > best_cover_len:
                        best_cover = candidate
                        best_cover_len = candidate_words

            if best_cover:
                rollup_map[pattern] = best_cover
                rollup_count += 1
                logger.debug(
                    f"Rollup: '{pattern}' ({len(pattern_tinyids)} tinyIds) "
                    f"→ '{best_cover[:60]}' ({len(pattern_to_tinyids[best_cover])} tinyIds)"
                )

        # Remove rolled-up patterns from kept set
        for pattern in rollup_map:
            kept_patterns.discard(pattern)

        if rollup_count:
            logger.info(f"TinyId-subset rollup: removed {rollup_count} short patterns")

    # Phase 2: Prefix extraction (if enabled)
    prefix_extracted_count = 0
    prefix_replacements: Dict[str, str] = {}  # original -> prefix pattern

    if min_prefix_tinyids > 0 and kept_patterns:
        logger.info(f"Extracting prefix patterns (min_tinyids={min_prefix_tinyids})...")

        # Build prefix trie from kept patterns
        # Each node tracks: tinyIds at this depth, patterns that pass through
        from dataclasses import dataclass, field as dc_field
        from typing import Set, Dict as TDict

        @dataclass
        class PrefixNode:
            children: TDict[str, 'PrefixNode'] = dc_field(default_factory=dict)
            tinyids: Set[str] = dc_field(default_factory=set)
            patterns: Set[str] = dc_field(default_factory=set)  # original patterns passing through
            depth: int = 0

        root = PrefixNode()

        # Insert all kept patterns into trie
        for pattern in kept_patterns:
            tokens = pattern.split()
            node = root
            for i, token in enumerate(tokens):
                if token not in node.children:
                    node.children[token] = PrefixNode(depth=i + 1)
                node = node.children[token]
                node.tinyids.update(pattern_to_tinyids[pattern])
                node.patterns.add(pattern)

        # Find deepest prefixes meeting threshold using greedy selection
        # Traverse trie and collect candidate prefixes
        candidates: List[Tuple[str, Set[str], Set[str]]] = []  # (prefix_pattern, tinyids, original_patterns)

        def collect_prefixes(node: PrefixNode, path: List[str]):
            if node.depth >= 2 and len(node.tinyids) >= min_prefix_tinyids:
                prefix_pattern = ' '.join(path)
                candidates.append((prefix_pattern, node.tinyids.copy(), node.patterns.copy()))

            for token, child in node.children.items():
                collect_prefixes(child, path + [token])

        collect_prefixes(root, [])

        # Sort by depth (longest first), then by tinyId count
        candidates.sort(key=lambda x: (-len(x[0].split()), -len(x[1])))

        # Greedy selection: longest prefixes that cover patterns
        covered_patterns: Set[str] = set()
        selected_prefixes: List[Tuple[str, Set[str], Set[str]]] = []

        for prefix_pattern, tinyids, original_patterns in candidates:
            # Only select if this prefix covers patterns not yet covered
            uncovered = original_patterns - covered_patterns
            if len(uncovered) >= 2:  # Must combine at least 2 patterns
                # Check if all uncovered patterns meet threshold
                combined_tinyids = set()
                for p in uncovered:
                    combined_tinyids.update(pattern_to_tinyids[p])

                if len(combined_tinyids) >= min_prefix_tinyids:
                    selected_prefixes.append((prefix_pattern, combined_tinyids, uncovered))
                    covered_patterns.update(uncovered)

        # Build replacement mapping and update kept_patterns
        new_patterns_from_prefix: Dict[str, Set[str]] = {}  # prefix -> combined tinyIds

        for prefix_pattern, combined_tinyids, original_patterns in selected_prefixes:
            for orig in original_patterns:
                if orig in kept_patterns:
                    kept_patterns.remove(orig)
                    prefix_replacements[orig] = prefix_pattern
                    prefix_extracted_count += 1

            # Merge tinyIds for the prefix pattern
            if prefix_pattern not in new_patterns_from_prefix:
                new_patterns_from_prefix[prefix_pattern] = set()
            new_patterns_from_prefix[prefix_pattern].update(combined_tinyids)

        # Add prefix patterns to kept_patterns and pattern_to_tinyids
        for prefix_pattern, tinyids in new_patterns_from_prefix.items():
            kept_patterns.add(prefix_pattern)
            pattern_to_tinyids[prefix_pattern] = tinyids

        logger.info(f"Prefix extraction: {prefix_extracted_count} patterns → "
                    f"{len(new_patterns_from_prefix)} prefix patterns")

    # For prefix-extracted patterns, propagate parent info from constituent patterns
    if has_parent_columns and prefix_replacements:
        for orig, prefix in prefix_replacements.items():
            if orig in pattern_to_parent and prefix not in pattern_to_parent:
                pattern_to_parent[prefix] = pattern_to_parent[orig]
                pattern_to_parent_count[prefix] = pattern_to_parent_count.get(orig, 0)

    # Phase 3: Emit definition-form variants (if enabled)
    # Patterns ending with " -" or " - " are designation-specific (e.g.,
    # "Center for Epidemiologic Studies-Depression Scale (CES-D) -").
    # Definitions use the same instrument name without the trailing separator
    # (e.g., "...Scale (CES-D)."). Emit both forms so stripping matches both fields.
    def_variant_count = 0

    if emit_def_variants and kept_patterns:
        logger.info("Emitting definition-form variants (stripping trailing ' -' / ' - ')...")
        new_variants: Dict[str, Set[str]] = {}
        for pattern in list(kept_patterns):
            stripped = pattern.rstrip()
            variant = None
            if stripped.endswith(' -'):
                variant = stripped[:-2].rstrip()
            elif stripped.endswith(' - '):
                variant = stripped[:-3].rstrip()

            if variant and variant not in kept_patterns and variant not in new_variants:
                new_variants[variant] = pattern_to_tinyids[pattern].copy()
                def_variant_count += 1
                logger.debug(
                    f"Def variant: '{pattern[:60]}' → '{variant[:60]}'"
                )

        # Add variants to kept set and tinyId map
        for variant, tinyids in new_variants.items():
            kept_patterns.add(variant)
            if variant in pattern_to_tinyids:
                pattern_to_tinyids[variant].update(tinyids)
            else:
                pattern_to_tinyids[variant] = tinyids
            # Propagate parent info from the dash-form
            # (parent info is inherited from the original pattern)

        if def_variant_count:
            logger.info(f"Definition variants: {def_variant_count} new patterns added")

    # Compute group_key for each kept pattern
    # Group key = longest shared word prefix with any other kept pattern (min 2 words)
    # Falls back to first 2 words if no shared prefix found
    pattern_group_keys: Dict[str, str] = {}
    kept_list = sorted(kept_patterns)
    for pattern in kept_list:
        tokens = pattern.split()
        best_prefix_len = 0
        for other in kept_list:
            if other == pattern:
                continue
            other_tokens = other.split()
            common = 0
            for a, b in zip(tokens, other_tokens):
                if a == b:
                    common += 1
                else:
                    break
            if common > best_prefix_len:
                best_prefix_len = common
        if best_prefix_len >= 2:
            pattern_group_keys[pattern] = ' '.join(tokens[:best_prefix_len])
        else:
            # Use first 2 words (or full pattern if shorter)
            pattern_group_keys[pattern] = ' '.join(tokens[:min(2, len(tokens))])

    # Write output (kept patterns only), sorted by group_key then pattern
    output_patterns = sorted(kept_patterns, key=lambda p: (pattern_group_keys.get(p, ''), p))
    with open(output_path, 'w', encoding='utf-8') as f:
        header = f"group_key\t{pattern_column}\t{tinyids_column}"
        if has_parent_columns:
            header += "\tparent_phrase\tparent_tinyid_count"
        f.write(header + "\n")
        for pattern in output_patterns:
            group_key = pattern_group_keys.get(pattern, "")
            tinyids_str = ' '.join(sorted(pattern_to_tinyids[pattern]))
            row = f"{group_key}\t{pattern}\t{tinyids_str}"
            if has_parent_columns:
                parent = pattern_to_parent.get(pattern, "")
                parent_count = pattern_to_parent_count.get(pattern, "")
                row += f"\t{parent}\t{parent_count}"
            f.write(row + "\n")

    # Write optional subsumption report (include prefix extractions)
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("type\toriginal_pattern\ttinyIds\treplacement\treplacement_tinyIds\n")

            # Write subsumptions
            for pattern, covers in sorted(subsumed.items(), key=lambda x: len(x[0])):
                pattern_tids = ' '.join(sorted(pattern_to_tinyids.get(pattern, set())))
                covers_str = ' | '.join(c[:60] for c in covers[:3])
                if len(covers) > 3:
                    covers_str += f" ... (+{len(covers)-3} more)"
                # Calculate union of covering tinyIds
                union_tids = set()
                for c in covers:
                    union_tids.update(pattern_to_tinyids.get(c, set()))
                union_str = ' '.join(sorted(union_tids))
                f.write(f"subsumed\t{pattern}\t{pattern_tids}\t{covers_str}\t{union_str}\n")

            # Write prefix extractions
            for orig, prefix in sorted(prefix_replacements.items(), key=lambda x: x[1]):
                orig_tids = ' '.join(sorted(pattern_to_tinyids.get(orig, set())))
                prefix_tids = ' '.join(sorted(pattern_to_tinyids.get(prefix, set())))
                f.write(f"prefix\t{orig}\t{orig_tids}\t{prefix}\t{prefix_tids}\n")

            # Write reverse subsumption (roll-down) entries
            for long_pat, base in sorted(reverse_subsumed.items(), key=lambda x: x[0]):
                long_tids = ' '.join(sorted(pattern_to_tinyids.get(long_pat, set())))
                base_tids = ' '.join(sorted(pattern_to_tinyids.get(base, set())))
                f.write(f"roll-down\t{long_pat}\t{long_tids}\t{base}\t{base_tids}\n")

            # Write rollup entries
            for orig, cover in sorted(rollup_map.items(), key=lambda x: x[0]):
                orig_tids = ' '.join(sorted(pattern_to_tinyids.get(orig, set())))
                cover_tids = ' '.join(sorted(pattern_to_tinyids.get(cover, set())))
                f.write(f"rollup\t{orig}\t{orig_tids}\t{cover}\t{cover_tids}\n")

            # Write anchor trimming entries
            for orig, bare in sorted(anchor_trimmed_map.items(), key=lambda x: x[0]):
                f.write(f"anchor-trim\t{orig}\t\t{bare}\t\n")

        logger.info(f"Wrote subsumption/prefix/rollup report to {report_path}")

    reverse_count = len(reverse_subsumed)
    stats = {
        'input_patterns': input_patterns,
        'output_patterns': len(kept_patterns),
        'subsumed_count': len(subsumed),
        'reverse_subsumed_count': reverse_count,
        'prefix_extracted_count': prefix_extracted_count,
        'rollup_count': rollup_count,
        'parent_filtered_count': parent_filtered_count,
        'anchor_trimmed_count': anchor_trimmed_count,
        'def_variant_count': def_variant_count,
        'subsumptions': list(subsumed.items())
    }

    anchor_info = f", {anchor_trimmed_count} anchor-trimmed" if anchor_trimmed_count else ""
    reverse_info = f", {reverse_count} roll-down" if reverse_count else ""
    rollup_info = f", {rollup_count} rolled-up" if rollup_count else ""
    parent_info = f", {parent_filtered_count} parent-filtered" if parent_filtered_count else ""
    logger.info(
        f"Coalesced {input_path}: {input_patterns} patterns → {len(kept_patterns)} kept "
        f"({len(subsumed)} subsumed{anchor_info}{reverse_info}, {prefix_extracted_count} prefix-extracted{rollup_info}{parent_info})"
    )

    return stats
