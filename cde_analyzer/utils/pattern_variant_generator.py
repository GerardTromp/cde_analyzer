"""
Pattern variant generator for instrument masking.

Generates spelling, punctuation, and spacing variants from base instrument patterns
to improve matching during pre-masking in phrase mining.

Option A implementation for addressing instrument masking failures caused by:
1. Spacing differences around parentheses: "Telephone (BTACT)" vs "Telephone(BTACT)"
2. Trailing punctuation: "(BTACT)" vs "(BTACT)."
3. Prefix variations: "as part of" vs "as part of the"
4. Acronym variations: "(RFQ)" vs "(RFQ-U)"
"""

import re
import logging
from typing import Set, List, Tuple, Optional

logger = logging.getLogger(__name__)


# Regex to match acronym at end of pattern: (ABC) or (ABC-D)
ACRONYM_SUFFIX_PATTERN = re.compile(r'\s*\(([A-Z][A-Z0-9]*(?:[-][A-Z0-9]+)*)\)\s*$')

# Common prefixes that introduce instruments
CONTEXT_PREFIXES = [
    "as part of the ",
    "as part of ",
    "as a part of the ",
    "as a part of ",
    "based on the ",
    "based on ",
    "from the ",
    "from ",
]

# Trailing punctuation that may vary
TRAILING_PUNCT = ['.', ',', ';', ':']

# Trailing punctuation with spaces (common in temporal phrases)
TRAILING_PUNCT_WITH_SPACE = [' - ', ': ', ', ']

# Number word mappings for temporal phrase variants (bidirectional)
NUMBER_WORDS = {
    '1': 'one',
    '2': 'two',
    '3': 'three',
    '4': 'four',
    '5': 'five',
    '6': 'six',
    '7': 'seven',
    '8': 'eight',
    '9': 'nine',
    '10': 'ten',
    '12': 'twelve',
    '14': 'fourteen',
    '24': 'twenty-four',
    '30': 'thirty',
    '60': 'sixty',
    '90': 'ninety',
}

# Reverse mapping (word → digit)
WORD_NUMBERS = {v: k for k, v in NUMBER_WORDS.items()}

# Words that commonly have possessive variants in instrument names
# Pattern: word → {word, word's, words} for handling extraction inconsistencies
POSSESSIVE_WORDS = [
    'parkinson',     # Parkinson's Disease
    'alzheimer',     # Alzheimer's Disease
    'crohn',         # Crohn's Disease
    'hodgkin',       # Hodgkin's Lymphoma
    'huntington',    # Huntington's Disease
    'addison',       # Addison's Disease
    'cushing',       # Cushing's Syndrome
    'raynaud',       # Raynaud's Phenomenon
    'sjogren',       # Sjögren's Syndrome
    'graves',        # Graves' Disease
    'bell',          # Bell's Palsy
    'meniere',       # Ménière's Disease
]

# Temporal words with singular/plural variants
TEMPORAL_PLURALS = {
    'day': 'days', 'days': 'day',
    'week': 'weeks', 'weeks': 'week',
    'month': 'months', 'months': 'month',
    'year': 'years', 'years': 'year',
}


def generate_case_variants(pattern: str) -> Set[str]:
    """
    Generate case variants: original + all-lowercase.

    'In the past 7 days' → {'In the past 7 days', 'in the past 7 days'}
    'PROMIS Depression' → {'PROMIS Depression', 'promis depression'}

    Covers the two main cases in CDE text: sentence-start (uppercase first
    letter) and mid-sentence (lowercase). Lowercase is additive — the
    original is always preserved, so acronyms are not lost.

    Args:
        pattern: Original pattern string

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}
    lower = pattern.lower()
    if lower != pattern:
        variants.add(lower)
    return variants


def generate_plural_variants(pattern: str) -> Set[str]:
    """
    Generate singular/plural variants for temporal words.

    'in the past 7 days' → {'in the past 7 days', 'in the past 7 day'}
    'past week scale' → {'past week scale', 'past weeks scale'}

    Uses word-boundary matching to avoid partial substitutions.
    Only handles temporal words (day/week/month/year).

    Args:
        pattern: Original pattern string

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}
    for singular, plural in TEMPORAL_PLURALS.items():
        word_re = re.compile(r'\b' + re.escape(singular) + r'\b')
        if word_re.search(pattern):
            new_pattern = word_re.sub(plural, pattern)
            variants.add(new_pattern)
    return variants


def generate_possessive_variants(pattern: str) -> Set[str]:
    """
    Generate possessive/non-possessive variants for disease names.

    'Parkinson' → {'Parkinson', "Parkinson's", 'Parkinsons'}
    "Parkinson's" → {'Parkinson', "Parkinson's", 'Parkinsons'}
    'Parkinsons' → {'Parkinson', "Parkinson's", 'Parkinsons'}

    Args:
        pattern: Original pattern string

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}
    pattern_lower = pattern.lower()

    for word in POSSESSIVE_WORDS:
        # Check for any form of the word
        forms = [
            (word, word),           # base: parkinson
            (word + "'s", word),    # possessive: parkinson's
            (word + "s", word),     # plural/typo: parkinsons
        ]

        for form, base in forms:
            idx = pattern_lower.find(form)
            if idx != -1:
                # Found this form - extract the actual casing from pattern
                actual_form = pattern[idx:idx + len(form)]
                # Determine the base with original casing
                if actual_form[0].isupper():
                    base_cased = base.capitalize()
                else:
                    base_cased = base

                # Generate all three variants with appropriate casing
                prefix = pattern[:idx]
                suffix = pattern[idx + len(form):]

                # Base form
                variants.add(prefix + base_cased + suffix)
                # Possessive form
                variants.add(prefix + base_cased + "'s" + suffix)
                # 's' form (common typo/variant)
                variants.add(prefix + base_cased + "s" + suffix)
                break  # Only process first match per word

    return variants


def generate_spacing_variants(pattern: str) -> Set[str]:
    """
    Generate spacing variants around parentheses.

    'Telephone (BTACT)' → {'Telephone (BTACT)', 'Telephone(BTACT)'}
    'Telephone(BTACT)' → {'Telephone(BTACT)', 'Telephone (BTACT)'}

    Args:
        pattern: Original pattern string

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}

    # Pattern for space before opening parenthesis
    # Match: "word (something)" or "word(something)"

    # Add/remove space before opening paren
    if ' (' in pattern:
        # Has space: also add version without
        variants.add(pattern.replace(' (', '('))

    # Find cases where there's no space before paren
    # Look for "letter(" pattern
    no_space_match = re.search(r'([a-zA-Z])\(', pattern)
    if no_space_match:
        # Add version with space
        variants.add(re.sub(r'([a-zA-Z])\(', r'\1 (', pattern))

    return variants


def generate_punctuation_variants(pattern: str) -> Set[str]:
    """
    Generate variants with and without trailing punctuation.

    '(BTACT).' → {'(BTACT).', '(BTACT)'}
    '(BTACT)' → {'(BTACT)', '(BTACT).', '(BTACT),'}
    'in the past 7 days' → {'in the past 7 days', 'in the past 7 days:', 'in the past 7 days - '}

    Args:
        pattern: Original pattern string

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}

    # Strip trailing punctuation (both simple and spaced) to get base
    base = pattern.rstrip(''.join(TRAILING_PUNCT))
    # Strip trailing whitespace BEFORE checking spaced punctuation
    # (patterns like "...SCS) - " end with dash-space, not space-dash)
    base = base.rstrip()
    # Also strip spaced punctuation endings (now correctly detects ' -', ':', etc.)
    for spaced_punct in TRAILING_PUNCT_WITH_SPACE:
        if base.endswith(spaced_punct.rstrip()):  # e.g., ends with ' -' or ':'
            base = base[:-len(spaced_punct.rstrip())]
    base = base.rstrip()  # Clean up any remaining trailing whitespace
    variants.add(base)

    # Add common trailing punctuation variants
    for punct in TRAILING_PUNCT:
        variants.add(base + punct)

    # Add spaced punctuation variants (common in temporal phrases)
    for spaced_punct in TRAILING_PUNCT_WITH_SPACE:
        variants.add(base + spaced_punct)

    return variants


def generate_number_variants(pattern: str) -> Set[str]:
    """
    Generate variants with digit/word number substitutions.

    'in the past 7 days' → {'in the past 7 days', 'in the past seven days'}
    'in the past seven days' → {'in the past seven days', 'in the past 7 days'}

    Handles common temporal numbers: 1-10, 12, 14, 24, 30, 60, 90

    Args:
        pattern: Original pattern string

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}

    # Try digit → word substitutions
    for digit, word in NUMBER_WORDS.items():
        # Use word boundaries to avoid partial matches
        # Match digit surrounded by non-digits (or start/end)
        digit_pattern = re.compile(r'(?<!\d)' + re.escape(digit) + r'(?!\d)')
        if digit_pattern.search(pattern):
            # Replace digit with word
            new_pattern = digit_pattern.sub(word, pattern)
            variants.add(new_pattern)

    # Try word → digit substitutions (case-insensitive)
    pattern_lower = pattern.lower()
    for word, digit in WORD_NUMBERS.items():
        # Find word in pattern (case-insensitive, word boundaries)
        word_pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        match = word_pattern.search(pattern)
        if match:
            # Replace word with digit, preserving surrounding text
            new_pattern = pattern[:match.start()] + digit + pattern[match.end():]
            variants.add(new_pattern)

    return variants


def generate_prefix_variants(pattern: str) -> Set[str]:
    """
    Generate variants with different context prefixes.

    'as part of the Risk Factor' → {
        'as part of the Risk Factor',
        'as part of Risk Factor',
        'as a part of the Risk Factor',
        'as a part of Risk Factor',
    }

    Args:
        pattern: Original pattern string

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}
    pattern_lower = pattern.lower()

    # Find which prefix this pattern uses
    for prefix in CONTEXT_PREFIXES:
        if pattern_lower.startswith(prefix):
            # Extract the instrument part (preserving case)
            instrument_part = pattern[len(prefix):]

            # Generate all prefix combinations
            for new_prefix in CONTEXT_PREFIXES:
                # Match case of first letter to original
                if pattern[0].isupper():
                    new_prefix_cased = new_prefix[0].upper() + new_prefix[1:]
                else:
                    new_prefix_cased = new_prefix
                variants.add(new_prefix_cased + instrument_part)

            break

    return variants


def generate_prefix_additions(pattern: str) -> Set[str]:
    """
    Add context prefixes to patterns that don't already have them.

    This ensures patterns like "Risk Factor Questionnaire (RFQ)" also match
    when they appear as "as part of the Risk Factor Questionnaire (RFQ)".

    'Risk Factor Questionnaire (RFQ)' → {
        'Risk Factor Questionnaire (RFQ)',
        'as part of Risk Factor Questionnaire (RFQ)',
        'as part of the Risk Factor Questionnaire (RFQ)',
        'as a part of Risk Factor Questionnaire (RFQ)',
        'as a part of the Risk Factor Questionnaire (RFQ)',
        'based on Risk Factor Questionnaire (RFQ)',
        'based on the Risk Factor Questionnaire (RFQ)',
        'from Risk Factor Questionnaire (RFQ)',
        'from the Risk Factor Questionnaire (RFQ)',
    }

    Args:
        pattern: Original pattern string (may or may not have prefix)

    Returns:
        Set of variant patterns including original, with prefixes added
    """
    variants = {pattern}
    pattern_lower = pattern.lower()

    # Check if pattern already has a prefix
    has_prefix = any(pattern_lower.startswith(prefix) for prefix in CONTEXT_PREFIXES)

    if not has_prefix:
        # Add all prefix variants
        for prefix in CONTEXT_PREFIXES:
            # Match case of first letter to the pattern's first letter
            if pattern and pattern[0].isupper():
                prefix_cased = prefix[0].upper() + prefix[1:]
            else:
                prefix_cased = prefix
            variants.add(prefix_cased + pattern)

    return variants


def extract_instrument_name_and_acronym(pattern: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract the instrument name and acronym from a pattern.

    'as part of the Risk Factor Questionnaire (RFQ)' →
        (prefix='as part of the ', name='Risk Factor Questionnaire', acronym='RFQ')

    Args:
        pattern: Full pattern string

    Returns:
        Tuple of (prefix, instrument_name, acronym) or (None, None, None) if no match
    """
    pattern_lower = pattern.lower()

    # Find prefix
    prefix = None
    remainder = pattern
    for p in CONTEXT_PREFIXES:
        if pattern_lower.startswith(p):
            prefix = pattern[:len(p)]
            remainder = pattern[len(p):]
            break

    # Find acronym at end
    acronym_match = ACRONYM_SUFFIX_PATTERN.search(remainder)
    if acronym_match:
        acronym = acronym_match.group(1)
        name = remainder[:acronym_match.start()].strip()
        return prefix, name, acronym

    return prefix, remainder.strip(), None


def generate_acronym_variants(pattern: str, known_acronym_variants: Optional[Set[str]] = None) -> Set[str]:
    """
    Generate variants with different acronym forms.

    If pattern has '(RFQ)' and known_variants contains 'RFQ-U', generate both.

    Args:
        pattern: Original pattern string
        known_acronym_variants: Optional set of known acronym variants to use

    Returns:
        Set of variant patterns including original
    """
    variants = {pattern}

    if not known_acronym_variants:
        return variants

    # Extract components
    prefix, name, acronym = extract_instrument_name_and_acronym(pattern)

    if name and known_acronym_variants:
        # Generate variants with each known acronym
        for variant_acronym in known_acronym_variants:
            if prefix:
                new_pattern = f"{prefix}{name} ({variant_acronym})"
            else:
                new_pattern = f"{name} ({variant_acronym})"
            variants.add(new_pattern)

    return variants


def generate_all_variants(
    pattern: str,
    known_acronym_variants: Optional[Set[str]] = None,
    include_name_only: bool = True,
    add_prefixes: bool = True,
    expand_numbers: bool = True
) -> Set[str]:
    """
    Generate all variant combinations for a pattern.

    Combines spacing, punctuation, prefix, possessive, acronym, and number variants.
    Optionally includes the bare instrument name for broader matching.
    Optionally adds context prefixes to patterns that don't have them.

    Args:
        pattern: Original pattern string
        known_acronym_variants: Optional set of known acronym variants
        include_name_only: If True, also include just the instrument name
                          (without prefix or acronym) for broader matching
        add_prefixes: If True, add context prefixes ("as part of", etc.) to
                     patterns that don't already have them. This ensures
                     patterns match both standalone and prefixed occurrences.
        expand_numbers: If True, generate digit/word number variants
                       (e.g., "7" ↔ "seven" for temporal phrases)

    Returns:
        Set of all variant patterns
    """
    all_variants = set()

    # First, handle prefix variants (interchange existing prefixes)
    prefix_variants = generate_prefix_variants(pattern)

    # Then, add prefixes to patterns that don't have them
    if add_prefixes:
        prefix_additions = set()
        for pv in prefix_variants:
            prefix_additions.update(generate_prefix_additions(pv))
        prefix_variants = prefix_additions

    for pv in prefix_variants:
        # Then possessive variants (Parkinson vs Parkinson's vs Parkinsons)
        possessive_variants = generate_possessive_variants(pv)

        for poss_v in possessive_variants:
            # Then acronym variants
            acronym_variants = generate_acronym_variants(poss_v, known_acronym_variants)

            for av in acronym_variants:
                # Then number variants (7 ↔ seven)
                if expand_numbers:
                    number_variants = generate_number_variants(av)
                else:
                    number_variants = {av}

                for nv in number_variants:
                    # Then spacing variants
                    spacing_variants = generate_spacing_variants(nv)

                    for sv in spacing_variants:
                        # Finally punctuation variants
                        punct_variants = generate_punctuation_variants(sv)
                        all_variants.update(punct_variants)

    # Optionally add just the instrument name
    if include_name_only:
        prefix, name, acronym = extract_instrument_name_and_acronym(pattern)
        if name:
            # Add bare name with possessive variants
            name_possessive_variants = generate_possessive_variants(name)
            for name_variant in name_possessive_variants:
                all_variants.add(name_variant)
                all_variants.update(generate_punctuation_variants(name_variant))
                if acronym:
                    # Also add "Name (ACRONYM)" without the prefix
                    with_acronym = f"{name_variant} ({acronym})"
                    all_variants.add(with_acronym)
                    all_variants.update(generate_spacing_variants(with_acronym))
                    all_variants.update(generate_punctuation_variants(with_acronym))

    return all_variants


def expand_pattern_set(
    patterns: Set[str],
    include_name_only: bool = True,
    collect_acronyms: bool = True,
    add_prefixes: bool = True,
    expand_numbers: bool = True
) -> Set[str]:
    """
    Expand a set of patterns by generating all variants for each.

    If collect_acronyms is True, first collects all acronyms from all patterns
    for each instrument name, then uses those to generate cross-variants.

    Args:
        patterns: Set of original patterns
        include_name_only: Include bare instrument names
        collect_acronyms: Collect and cross-reference acronyms across patterns
        add_prefixes: Add context prefixes ("as part of", etc.) to patterns
                     that don't already have them
        expand_numbers: If True, generate digit/word number variants
                       (e.g., "7" ↔ "seven" for temporal phrases)

    Returns:
        Expanded set of all variant patterns
    """
    # First pass: collect acronyms per normalized instrument name
    name_to_acronyms = {}
    if collect_acronyms:
        for pattern in patterns:
            prefix, name, acronym = extract_instrument_name_and_acronym(pattern)
            if name and acronym:
                norm_name = name.lower()
                if norm_name not in name_to_acronyms:
                    name_to_acronyms[norm_name] = set()
                name_to_acronyms[norm_name].add(acronym)

    # Second pass: generate all variants
    all_variants = set()
    for pattern in patterns:
        # Get known acronyms for this instrument
        prefix, name, acronym = extract_instrument_name_and_acronym(pattern)
        known_acronyms = None
        if name and collect_acronyms:
            norm_name = name.lower()
            known_acronyms = name_to_acronyms.get(norm_name)

        variants = generate_all_variants(
            pattern,
            known_acronym_variants=known_acronyms,
            include_name_only=include_name_only,
            add_prefixes=add_prefixes,
            expand_numbers=expand_numbers
        )
        all_variants.update(variants)

    logger.info(f"Expanded {len(patterns)} patterns to {len(all_variants)} variants")
    return all_variants


def load_and_expand_patterns(
    filepath: str,
    column_name: str = 'full_match',
    expand_variants: bool = True,
    include_name_only: bool = True,
    add_prefixes: bool = True,
    expand_numbers: bool = True
) -> Set[str]:
    """
    Load patterns from TSV file and optionally expand with variants.

    This is a convenience wrapper for use in phrase_miner.

    Args:
        filepath: Path to TSV file
        column_name: Column to read patterns from
        expand_variants: If True, generate all variants
        include_name_only: Include bare instrument names
        add_prefixes: Add context prefixes ("as part of", etc.) to patterns
                     that don't already have them
        expand_numbers: If True, generate digit/word number variants
                       (e.g., "7" ↔ "seven" for temporal phrases)

    Returns:
        Set of patterns (expanded if requested)
    """
    from pathlib import Path

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Instrument list file not found: {filepath}")

    patterns = set()
    with path.open('r', encoding='utf-8') as f:
        # Read header to find column index
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        try:
            col_idx = headers.index(column_name)
        except ValueError:
            raise ValueError(
                f"Column '{column_name}' not found in {filepath}. "
                f"Available columns: {', '.join(headers)}"
            )

        # Read data rows
        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')
            if col_idx < len(fields):
                pattern = fields[col_idx].strip()
                if pattern:
                    patterns.add(pattern)

    logger.info(f"Loaded {len(patterns)} base patterns from {filepath}")

    if expand_variants:
        patterns = expand_pattern_set(
            patterns,
            include_name_only=include_name_only,
            collect_acronyms=True,
            add_prefixes=add_prefixes,
            expand_numbers=expand_numbers
        )

    return patterns
