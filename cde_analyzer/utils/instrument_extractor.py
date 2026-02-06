"""
Instrument pattern extraction for phrase_miner.

Detects and extracts structured references to research instruments,
questionnaires, and surveys using the pattern:
    "as part of [version X.X of] [the] <Instrument Name> [(<ACRONYM>)]"

These patterns are common in CDE data and represent high-value metadata
about the source questionnaires. Pre-extracting these patterns before
k-mer mining:
1. Produces clean instrument metadata
2. Reduces noise from piecemeal phrase detection
3. Ensures complete instrument names are captured

Supplementary patterns (Jan 2026):
Non-Title-Case patterns discovered in CDE corpus that the main regex misses.
These patterns are loaded from two locations:
  1. Global config: config/supplementary_patterns.yaml (in project)
  2. Local override: ./supplementary_patterns.yaml (in working directory)
Local files extend the global list for rapid iteration during curation.
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# Cached supplementary patterns (loaded lazily from config file)
_supplementary_patterns_cache: Optional[List[Tuple[str, str, Optional[str]]]] = None


def get_supplementary_patterns() -> List[Tuple[str, str, Optional[str]]]:
    """
    Load supplementary patterns from config files.

    Patterns are loaded from two locations (later extends earlier):
      1. Global config: config/supplementary_patterns.yaml (in project)
      2. Local override: ./supplementary_patterns.yaml (in working directory)

    Local files extend the global list, allowing rapid iteration during
    curation without modifying installed code.

    Patterns are cached after first load. Use clear_supplementary_patterns_cache()
    to force reload if config files change.

    Returns:
        List of (pattern_text, display_name, acronym) tuples.
    """
    global _supplementary_patterns_cache

    if _supplementary_patterns_cache is not None:
        return _supplementary_patterns_cache

    try:
        from utils.config_loader import load_supplementary_patterns, get_config_dir
        config_dir = get_config_dir()
        logger.debug(f"Loading supplementary patterns from: {config_dir / 'supplementary_patterns.yaml'} + local override")
        _supplementary_patterns_cache = load_supplementary_patterns()
        logger.info(f"Loaded {len(_supplementary_patterns_cache)} supplementary patterns total")
    except ImportError as e:
        logger.warning(f"Config loader not available ({e}), using empty supplementary patterns")
        _supplementary_patterns_cache = []

    return _supplementary_patterns_cache


def clear_supplementary_patterns_cache():
    """
    Clear the cached supplementary patterns to force reload.

    Also clears the underlying config_loader cache to ensure fresh reads
    from both global and local config files.
    """
    global _supplementary_patterns_cache
    _supplementary_patterns_cache = None

    # Also clear config_loader cache for supplementary_patterns
    try:
        from utils.config_loader import clear_config_cache
        clear_config_cache()
    except ImportError:
        pass


@dataclass
class VariantInfo:
    """Information about a spelling variant."""
    variant_name: str          # The variant (typo) form
    variant_type: str          # deletion, insertion, substitution, case, mixed
    differences: List[str]     # Human-readable description of each difference
    tinyIds: List[str] = field(default_factory=list)  # CDEs containing this variant


def classify_variant_type(canonical: str, variant: str) -> VariantInfo:
    """
    Classify the type of spelling difference between canonical and variant.

    Uses SequenceMatcher opcodes to identify:
    - deletion: variant is missing letter(s) - e.g., "Concusion" vs "Concussion"
    - insertion: variant has extra letter(s) - e.g., "Questionnnaire" vs "Questionnaire"
    - substitution: variant has wrong letter(s) - e.g., "Transcraniam" vs "Transcranial"
    - case: only case differs - e.g., "PROMIS" vs "Promis"
    - mixed: multiple types of differences

    Args:
        canonical: The correct/canonical form
        variant: The variant (typo) form

    Returns:
        VariantInfo with variant_type and list of differences
    """
    # Check for case-only difference first
    if canonical.lower() == variant.lower():
        return VariantInfo(
            variant_name=variant,
            variant_type="case",
            differences=[f"case differs: '{variant}' vs '{canonical}'"]
        )

    # Use SequenceMatcher to get edit operations
    matcher = SequenceMatcher(None, canonical.lower(), variant.lower())
    opcodes = matcher.get_opcodes()

    deletions = []
    insertions = []
    substitutions = []

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'delete':
            # Characters in canonical that are missing from variant
            deleted_chars = canonical[i1:i2]
            deletions.append(f"missing '{deleted_chars}' at position {i1}")
        elif tag == 'insert':
            # Extra characters in variant not in canonical
            inserted_chars = variant[j1:j2]
            insertions.append(f"extra '{inserted_chars}' at position {j1}")
        elif tag == 'replace':
            # Characters differ between canonical and variant
            orig_chars = canonical[i1:i2]
            new_chars = variant[j1:j2]
            substitutions.append(f"'{orig_chars}' -> '{new_chars}' at position {i1}")

    # Classify based on what types of edits were found
    differences = []
    types_found = []

    if deletions:
        types_found.append("deletion")
        differences.extend(deletions)
    if insertions:
        types_found.append("insertion")
        differences.extend(insertions)
    if substitutions:
        types_found.append("substitution")
        differences.extend(substitutions)

    if len(types_found) == 0:
        # Shouldn't happen, but fallback
        variant_type = "other"
    elif len(types_found) == 1:
        variant_type = types_found[0]
    else:
        variant_type = "mixed"

    return VariantInfo(
        variant_name=variant,
        variant_type=variant_type,
        differences=differences
    )


@dataclass
class InstrumentMatch:
    """Represents a detected instrument reference in text."""
    full_match: str                          # Complete matched text
    instrument_name: str                     # Extracted instrument name (Title Case)
    acronym: Optional[str]                   # Parenthetical acronym if present
    char_span: Tuple[int, int]              # (start, end) character offsets in source
    token_span: Optional[Tuple[int, int]] = None  # (start, end) token indices
    tinyId: Optional[str] = None            # Source CDE identifier
    field_path: Optional[str] = None        # Source field path
    # Family identification fields (populated when detect_families=True)
    family_id: Optional[str] = None         # e.g., "neuro-qol"
    family_display_name: Optional[str] = None  # e.g., "Neuro-QOL"
    instrument_id: Optional[str] = None     # e.g., "instrument_0001"
    family_confidence: Optional[float] = None  # 0.0-1.0 confidence in family assignment
    identification_method: Optional[str] = None  # "pattern", "llm", "manual"
    needs_review: bool = False              # True if confidence < threshold
    # Subinstrument fields (for hierarchical instruments like PROMIS subscales)
    subinstrument_name: Optional[str] = None  # e.g., "Pain Interference"
    subinstrument_id: Optional[str] = None    # e.g., "pain-interference"


@dataclass
class InstrumentCatalog:
    """Collection of detected instruments across the corpus."""
    instruments: Dict[str, List[InstrumentMatch]] = field(default_factory=dict)
    # Keyed by normalized instrument name

    def add(self, match: InstrumentMatch) -> None:
        """Add a match, grouping by normalized name."""
        key = normalize_instrument_name(match.instrument_name)
        if key not in self.instruments:
            self.instruments[key] = []
        self.instruments[key].append(match)

    def get_distinct_tinyids(self, instrument_key: str) -> Set[str]:
        """Get unique tinyIds for an instrument."""
        matches = self.instruments.get(instrument_key, [])
        return {m.tinyId for m in matches if m.tinyId}

    def get_all_token_spans(self) -> List[Tuple[str, str, Tuple[int, int]]]:
        """
        Get all token spans for masking.

        Returns:
            List of (tinyId, field_path, token_span) tuples
        """
        spans = []
        for matches in self.instruments.values():
            for m in matches:
                if m.token_span and m.tinyId and m.field_path:
                    spans.append((m.tinyId, m.field_path, m.token_span))
        return spans

    def get_acronym_to_name_map(self) -> Dict[str, str]:
        """
        Build a mapping from acronyms to canonical instrument names.

        When multiple instruments share the same acronym, prefers the most
        frequently occurring instrument.

        Returns:
            Dict mapping acronym -> canonical instrument name
        """
        acronym_to_names: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

        for normalized_name, matches in self.instruments.items():
            if not matches:
                continue

            # Get the most common acronym for this instrument
            acronyms = [m.acronym for m in matches if m.acronym]
            if not acronyms:
                continue

            # Use the first match's instrument_name as canonical
            canonical_name = matches[0].instrument_name
            count = len(matches)

            for acronym in set(acronyms):
                acronym_to_names[acronym].append((canonical_name, count))

        # For each acronym, pick the instrument with highest frequency
        result = {}
        for acronym, name_counts in acronym_to_names.items():
            # Sort by count descending, take first
            name_counts.sort(key=lambda x: x[1], reverse=True)
            result[acronym] = name_counts[0][0]

        return result

    def assign_families(self, confidence_threshold: float = 0.7) -> None:
        """
        Assign family identification to all instruments using pattern detection.

        Assigns sequential instrument_ids (instrument_0001, instrument_0002, etc.)
        sorted by normalized instrument name for deterministic ordering.

        Args:
            confidence_threshold: Minimum confidence for automatic acceptance.
                Below this threshold, instruments are flagged for review.
        """
        from utils.instrument_family_patterns import InstrumentFamilyDetector

        detector = InstrumentFamilyDetector(confidence_threshold=confidence_threshold)

        # Sort instrument keys for deterministic sequential numbering
        sorted_keys = sorted(self.instruments.keys())

        for instrument_number, key in enumerate(sorted_keys, start=1):
            matches = self.instruments[key]
            for match in matches:
                # Detect family and generate identification
                result = detector.detect_and_identify(
                    instrument_name=match.instrument_name,
                    full_match=match.full_match,
                    acronym=match.acronym,
                    instrument_number=instrument_number,
                )
                # Populate family fields
                match.family_id = result["family_id"]
                match.family_display_name = result["family_display_name"]
                match.instrument_id = result["instrument_id"]
                match.family_confidence = result["family_confidence"]
                match.identification_method = result["identification_method"]
                match.needs_review = result["needs_review"]

    def merge_spelling_variants(
        self,
        similarity_threshold: float = 0.85,
        min_length: int = 10,
    ) -> Dict[str, List[VariantInfo]]:
        """
        Merge spelling variants (typos) into canonical forms.

        Uses edit distance to identify similar instrument names that are likely
        typos of each other (e.g., "Transcraniam" vs "Transcranial").

        Strategy:
        1. Group instruments by same acronym (if present) - likely same instrument
        2. Within each group, compute similarity between normalized names
        3. Merge similar names (above threshold) into the most frequent form
        4. Short names (< min_length) must have higher similarity to avoid false merges

        Args:
            similarity_threshold: Minimum similarity ratio (0-1) to consider a merge.
                Default 0.85 means 85% similar.
            min_length: Minimum normalized name length for standard threshold.
                Shorter names use higher threshold (0.95) to avoid false merges.

        Returns:
            Dict mapping canonical normalized name to list of VariantInfo objects
            with variant names and their classified types (deletion, insertion,
            substitution, case, mixed)
        """
        merged_variants: Dict[str, List[VariantInfo]] = {}
        keys_to_remove = []

        # Group instruments by acronym for more targeted comparison
        acronym_groups: Dict[Optional[str], List[str]] = defaultdict(list)
        for norm_name, matches in self.instruments.items():
            # Get the most common acronym for this instrument
            acronyms = [m.acronym for m in matches if m.acronym]
            primary_acronym = max(set(acronyms), key=acronyms.count) if acronyms else None
            acronym_groups[primary_acronym].append(norm_name)

        for acronym, norm_names in acronym_groups.items():
            if len(norm_names) < 2:
                continue

            # For instruments with same acronym, check similarity
            # Sort by frequency (descending) so we prefer more common forms
            sorted_names = sorted(
                norm_names,
                key=lambda n: len(self.instruments[n]),
                reverse=True
            )

            # Track which names have been merged
            merged_into: Dict[str, str] = {}

            for i, name1 in enumerate(sorted_names):
                if name1 in merged_into:
                    continue

                for name2 in sorted_names[i + 1:]:
                    if name2 in merged_into:
                        continue

                    # Compute similarity
                    ratio = SequenceMatcher(None, name1, name2).ratio()

                    # Use higher threshold for short names
                    effective_threshold = similarity_threshold
                    if len(name1) < min_length or len(name2) < min_length:
                        effective_threshold = 0.95

                    if ratio >= effective_threshold:
                        # Merge name2 into name1 (name1 is more frequent)
                        merged_into[name2] = name1

                        # Collect tinyIds from the variant's matches BEFORE merging
                        variant_tinyIds = sorted({
                            m.tinyId for m in self.instruments[name2] if m.tinyId
                        })

                        # Classify the variant type
                        variant_info = classify_variant_type(name1, name2)
                        variant_info.tinyIds = variant_tinyIds

                        if name1 not in merged_variants:
                            merged_variants[name1] = []
                        merged_variants[name1].append(variant_info)

                        logger.debug(
                            f"Merging spelling variant: '{name2}' -> '{name1}' "
                            f"(type={variant_info.variant_type}, similarity={ratio:.3f}, "
                            f"acronym={acronym}, n_tinyIds={len(variant_tinyIds)})"
                        )

            # Perform the actual merges
            for variant_name, canonical_name in merged_into.items():
                # Move all matches from variant to canonical
                variant_matches = self.instruments.pop(variant_name, [])
                self.instruments[canonical_name].extend(variant_matches)
                keys_to_remove.append(variant_name)

        if merged_variants:
            total_merged = sum(len(v) for v in merged_variants.values())
            logger.info(
                f"Merged {total_merged} spelling variants into "
                f"{len(merged_variants)} canonical forms"
            )

        return merged_variants

    def get_families_summary(self) -> Dict[str, Dict]:
        """
        Get summary statistics grouped by family.

        Returns:
            Dict mapping family_id to summary dict with:
            - display_name: Human-readable family name
            - n_instruments: Count of distinct instruments
            - n_tinyids: Total distinct documents
            - total_frequency: Sum of all occurrences
            - instruments: List of canonical instrument names
            - acronyms: Set of all acronyms
        """
        families: Dict[str, Dict] = {}

        for normalized_name, matches in self.instruments.items():
            if not matches:
                continue

            # Get family from first match (all should have same family)
            first_match = matches[0]
            family_id = first_match.family_id or "unknown"
            display_name = first_match.family_display_name or "Unknown"

            if family_id not in families:
                families[family_id] = {
                    "display_name": display_name,
                    "n_instruments": 0,
                    "n_tinyids": 0,
                    "total_frequency": 0,
                    "instruments": [],
                    "acronyms": set(),
                    "_tinyids": set(),  # Internal tracking
                }

            # Aggregate stats
            families[family_id]["n_instruments"] += 1
            families[family_id]["instruments"].append(first_match.instrument_name)
            families[family_id]["total_frequency"] += len(matches)

            for m in matches:
                if m.tinyId:
                    families[family_id]["_tinyids"].add(m.tinyId)
                if m.acronym:
                    families[family_id]["acronyms"].add(m.acronym)

        # Finalize tinyid counts and convert sets
        for family_id, data in families.items():
            data["n_tinyids"] = len(data["_tinyids"])
            data["acronyms"] = sorted(data["acronyms"])
            del data["_tinyids"]

        return families


def normalize_instrument_name(name: str) -> str:
    """
    Normalize instrument name for grouping.

    Converts to lowercase, collapses whitespace, removes hyphens.
    This allows grouping of slight variations like:
    - "Short Form Health Survey" and "Short-Form Health Survey"
    """
    return " ".join(name.lower().split()).replace("-", " ")


class InstrumentExtractor:
    """
    Extracts instrument patterns from text using regex and heuristics.

    Detects patterns like:
    - "as part of Patient Health Questionnaire"
    - "as a part of the Drug Abuse Screening Test (DAST)"
    - "as part of version 1.0 of 36-item Short Form Health Survey (SF-36)"
    - "based on Multiple Sclerosis Quality of Life Scale"
    - "field of the NIH Toolbox Cognitive Battery"
    """

    # Pattern components

    # Optional version clause: "version 1.0 of" or "version 2 of"
    VERSION_PATTERN = r'(?:version\s+[\d.]+\s+of\s+)?'

    # Optional article: "the"
    ARTICLE_PATTERN = r'(?:the\s+)?'

    # Optional numbered prefix: "36-item" or "12-question"
    NUMBERED_PREFIX = r'(?:\d+[-\s](?:item|question|point)\s+)?'

    # Title Case word: starts with uppercase, followed by lowercase/digits
    # Allows hyphenated compounds like "Self-Report" or "Kiddie-Schedule"
    # Also handles mixed-case hyphenated words like "Neuro-QOL" where suffix is ALL CAPS
    TITLE_CASE_WORD = r"[A-Z][a-z0-9]*(?:'s)?(?:-[A-Za-z][A-Za-z0-9]*)*"

    # All-caps word: abbreviations like "TBI", "PTSD", or Roman numerals like "III", "IV"
    # Must be 2+ chars to avoid matching single letters that should be lowercase (e.g., "a")
    ALL_CAPS_WORD = r'[A-Z][A-Z0-9]+'

    # Lowercase connector words commonly found in instrument names
    # e.g., "of", "and", "for", "the", "in", "on", "to", "a"
    CONNECTOR_WORD = r'[a-z]+'

    # Any word in instrument name: ALL CAPS, Title Case, or lowercase connector
    # IMPORTANT: ALL_CAPS_WORD must come FIRST so "TBI" matches as ALL_CAPS, not "T" as Title Case
    INSTRUMENT_WORD = rf'(?:{ALL_CAPS_WORD}|{TITLE_CASE_WORD}|{CONNECTOR_WORD})'

    # Instrument name: sequence starting with a capitalized word, followed by more words
    # Can start with ALL CAPS OR Title Case to handle names like "PTSD Checklist"
    # IMPORTANT: ALL_CAPS_WORD must come FIRST for same reason as above
    INSTRUMENT_START = rf'(?:{ALL_CAPS_WORD}|{TITLE_CASE_WORD})'
    # Word separator: whitespace, optionally with hyphen/dash (for names like "Movement Disorder Society - Unified Parkinson's")
    WORD_SEPARATOR = r'(?:\s+-\s+|\s+)'
    INSTRUMENT_NAME = rf'({INSTRUMENT_START}(?:{WORD_SEPARATOR}{INSTRUMENT_WORD})+)'

    # Optional acronym in parentheses: (SF-36), (DAST), (PHQ-9), (K-SADS-PL)
    # Allows multiple hyphenated segments for complex acronyms
    # Also support space-separated acronyms like (MDS UPDRS)
    ACRONYM_PATTERN = r'(?:\s*\(([A-Z][A-Z0-9]*(?:[-\s][A-Z0-9]+)*)\))?'

    # Introductory pattern variations:
    # 1. "as part of" / "as a part of" - most common
    # 2. "based on" - used for quality-of-life scales
    # 3. "field of" - used for NIH Toolbox composite fields
    AS_PART_OF = r'[Aa][Ss]\s+(?:[Aa]\s+)?[Pp][Aa][Rr][Tt]\s+[Oo][Ff]\s+'  # "as part of" or "as a part of"
    BASED_ON = r'[Bb][Aa][Ss][Ee][Dd]\s+[Oo][Nn]\s+'  # "based on"
    FIELD_OF = r'[Ff][Ii][Ee][Ll][Dd]\s+[Oo][Ff]\s+'  # "field of"

    # Full pattern: multiple introductory patterns, case-sensitive for instrument name
    FULL_PATTERN = re.compile(
        rf'(?:{AS_PART_OF}|{BASED_ON}|{FIELD_OF})' +
        VERSION_PATTERN +
        ARTICLE_PATTERN +
        NUMBERED_PREFIX +
        INSTRUMENT_NAME +
        ACRONYM_PATTERN
    )

    # Abbreviation-only pattern: "as part of (ACRONYM)" without full instrument name
    # This catches references like "as part of (PHQ-9)" or "as part of the (DAST)"
    # Acronym must be 2+ chars, optionally with hyphen-separated suffixes
    ABBREV_ONLY_PATTERN = re.compile(
        rf'(?:{AS_PART_OF}|{BASED_ON}|{FIELD_OF})' +
        r'(?:the\s+)?' +  # Optional "the"
        r'\(([A-Z][A-Z0-9]*(?:[-][A-Z0-9]+)*)\)'  # Acronym in parentheses (captured)
    )

    def __init__(self, min_name_words: int = 3):
        """
        Initialize the instrument extractor.

        Args:
            min_name_words: Minimum words required in instrument name (default 3)
        """
        self.min_name_words = min_name_words

    def extract_from_text(
        self,
        text: str,
        tinyId: Optional[str] = None,
        field_path: Optional[str] = None
    ) -> List[InstrumentMatch]:
        """
        Extract all instrument matches from text.

        Args:
            text: Source text to scan
            tinyId: Optional CDE identifier for tracking
            field_path: Optional field path for tracking

        Returns:
            List of InstrumentMatch objects (may be empty)
        """
        if not text:
            return []

        matches = []

        for m in self.FULL_PATTERN.finditer(text):
            instrument_name = m.group(1)
            acronym = m.group(2) if m.lastindex >= 2 and m.group(2) else None

            # Validate: instrument name must meet Title Case criteria
            if not self._is_valid_instrument_name(instrument_name):
                continue

            match = InstrumentMatch(
                full_match=m.group(0),
                instrument_name=instrument_name.strip(),
                acronym=acronym,
                char_span=(m.start(), m.end()),
                tinyId=tinyId,
                field_path=field_path
            )
            matches.append(match)

        return matches

    # APA-style minor words: short conjunctions, prepositions, articles (3 letters or fewer)
    # Per APA 7th edition (Section 6.17): lowercase minor words unless first word of title/subtitle
    # See: https://apastyle.apa.org/style-grammar-guidelines/capitalization/title-case
    MINOR_WORDS = frozenset({
        # Articles
        'a', 'an', 'the',
        # Short conjunctions (APA 7th ed. explicitly lists: and, as, but, for, if, nor, or, so, yet)
        'and', 'as', 'but', 'for', 'if', 'nor', 'or', 'so', 'yet',
        # Short prepositions (APA 7th ed. lists: as, at, by, for, in, of, off, on, per, to, up, via)
        'at', 'by', 'in', 'of', 'off', 'on', 'per', 'to', 'up', 'via',
    })

    def _is_valid_instrument_name(self, name: str) -> bool:
        """
        Validate that instrument name meets Title Case criteria.

        Uses APA-style rules where:
        - Major words (nouns, verbs, adjectives, adverbs, 4+ letters) should be Title Case
        - Minor words (short conjunctions, prepositions, articles) may be lowercase
        - ALL CAPS words (abbreviations like TBI, PTSD, Roman numerals like III) are acceptable

        Requirements:
        - At least min_name_words words
        - At least 60% of words should be correctly cased
        - Minor words in lowercase count as correct
        - ALL CAPS words (2+ letters) count as correct

        Args:
            name: Instrument name to validate

        Returns:
            True if name meets criteria
        """
        words = name.split()
        if len(words) < self.min_name_words:
            return False

        # Count words that are correctly cased
        # Major words should be Title Case or ALL CAPS, minor words can be lowercase
        correct_count = 0
        for word in words:
            word_lower = word.lower()
            alpha_part = ''.join(c for c in word if c.isalpha())

            if word_lower in self.MINOR_WORDS:
                # Minor word: correct if lowercase (as expected in Title Case)
                correct_count += 1
            elif alpha_part and len(alpha_part) >= 2 and alpha_part.isupper():
                # ALL CAPS word (abbreviation or Roman numeral): always correct
                correct_count += 1
            elif alpha_part and alpha_part[0].isupper():
                # Major word: correct if Title Case (first letter upper)
                correct_count += 1

        # Require more than 60% correctly cased (strict: > 0.6)
        return correct_count / len(words) > 0.6

    def extract_abbreviation_only(
        self,
        text: str,
        known_acronyms: Optional[Dict[str, str]] = None,
        tinyId: Optional[str] = None,
        field_path: Optional[str] = None
    ) -> List[InstrumentMatch]:
        """
        Extract abbreviation-only instrument matches from text.

        Finds patterns like "as part of (PHQ-9)" where only the acronym is used.
        If known_acronyms is provided, maps the acronym to its canonical name.

        Args:
            text: Source text to scan
            known_acronyms: Optional dict mapping acronym -> canonical instrument name
            tinyId: Optional CDE identifier for tracking
            field_path: Optional field path for tracking

        Returns:
            List of InstrumentMatch objects for abbreviation-only references
        """
        if not text:
            return []

        matches = []

        for m in self.ABBREV_ONLY_PATTERN.finditer(text):
            acronym = m.group(1)

            # Look up canonical name if known
            if known_acronyms and acronym in known_acronyms:
                instrument_name = known_acronyms[acronym]
            else:
                # Use acronym as the instrument name
                instrument_name = f"[{acronym}]"

            match = InstrumentMatch(
                full_match=m.group(0),
                instrument_name=instrument_name,
                acronym=acronym,
                char_span=(m.start(), m.end()),
                tinyId=tinyId,
                field_path=field_path
            )
            matches.append(match)

        return matches

    def extract_supplementary_patterns(
        self,
        text: str,
        tinyId: Optional[str] = None,
        field_path: Optional[str] = None
    ) -> List[InstrumentMatch]:
        """
        Extract supplementary instrument patterns that don't match Title Case rules.

        These patterns were discovered in the CDE corpus but use non-standard
        capitalization (e.g., "as part of Partition test" with lowercase "test").

        Args:
            text: Source text to scan
            tinyId: Optional CDE identifier for tracking
            field_path: Optional field path for tracking

        Returns:
            List of InstrumentMatch objects for supplementary patterns found
        """
        if not text:
            return []

        matches = []

        # Load patterns from config file (cached)
        supplementary_patterns = get_supplementary_patterns()
        if not supplementary_patterns:
            return matches

        # Build patterns with anchor prefixes
        for pattern_text, display_name, acronym in supplementary_patterns:
            # Match with various anchor prefixes (case-insensitive for anchor)
            for anchor in ['as part of ', 'as a part of ', 'based on ', 'field of ']:
                # Also try with "the " after anchor
                for the_prefix in ['', 'the ']:
                    full_pattern = anchor + the_prefix + pattern_text
                    # Case-insensitive search for the full pattern
                    idx = text.lower().find(full_pattern.lower())
                    if idx >= 0:
                        # Extract actual matched text (preserving original case)
                        actual_match = text[idx:idx + len(full_pattern)]
                        match = InstrumentMatch(
                            full_match=actual_match,
                            instrument_name=display_name,
                            acronym=acronym,
                            char_span=(idx, idx + len(actual_match)),
                            tinyId=tinyId,
                            field_path=field_path
                        )
                        matches.append(match)

        return matches

    def compute_token_spans(
        self,
        matches: List[InstrumentMatch],
        char_offsets: List[Tuple[int, int]]
    ) -> List[InstrumentMatch]:
        """
        Add token span information to matches based on character offsets.

        Maps character spans to token indices for masking during k-mer mining.

        Args:
            matches: List of matches with char_span populated
            char_offsets: List of (start, end) char positions per token

        Returns:
            Same matches with token_span populated
        """
        if not char_offsets:
            return matches

        for match in matches:
            char_start, char_end = match.char_span

            # Find first token that overlaps with char_start
            start_token = None
            for i, (cs, ce) in enumerate(char_offsets):
                # Token overlaps if: token contains char_start OR token starts within match
                if cs <= char_start < ce or (char_start <= cs < char_end):
                    start_token = i
                    break

            # Find last token that overlaps with char_end
            end_token = None
            for i, (cs, ce) in enumerate(char_offsets):
                # Token is part of match if it starts before char_end
                if cs < char_end:
                    end_token = i + 1  # Exclusive end

            if start_token is not None and end_token is not None:
                match.token_span = (start_token, end_token)

        return matches


def extract_instruments_from_items(
    items: list,
    field_names: List[str],
    min_name_words: int = 3,
    extract_abbreviation_only: bool = False,
    extract_supplementary: bool = False
) -> InstrumentCatalog:
    """
    Extract instruments from a list of CDE items.

    Convenience function for batch processing.

    Args:
        items: List of CDEItem objects
        field_names: Field names to extract from
        min_name_words: Minimum words in instrument name
        extract_abbreviation_only: If True, perform a second pass to extract
            abbreviation-only references like "as part of (PHQ-9)". Uses
            acronyms from the first pass to map to canonical names.
        extract_supplementary: If True, perform a third pass to extract
            supplementary patterns (non-Title-Case instruments like animal
            behavioral tests). See SUPPLEMENTARY_PATTERNS constant.

    Returns:
        InstrumentCatalog with all detected instruments
    """
    from utils.field_extractor import extract_field_texts

    extractor = InstrumentExtractor(min_name_words=min_name_words)
    catalog = InstrumentCatalog()

    # First pass: extract full instrument patterns
    # Also collect text spans for potential subsequent passes
    text_spans_by_item = []
    for item in items:
        text_spans = extract_field_texts(item, field_names)
        text_spans_by_item.append((item, text_spans))
        for field_path, text in text_spans:
            matches = extractor.extract_from_text(
                text,
                tinyId=getattr(item, 'tinyId', None),
                field_path=field_path
            )
            for match in matches:
                catalog.add(match)

    # Second pass: extract abbreviation-only patterns
    if extract_abbreviation_only:
        # Build acronym -> canonical name mapping from first pass
        acronym_map = catalog.get_acronym_to_name_map()
        logger.info(f"Built acronym map with {len(acronym_map)} known acronyms")

        abbrev_count = 0
        for item, text_spans in text_spans_by_item:
            for field_path, text in text_spans:
                matches = extractor.extract_abbreviation_only(
                    text,
                    known_acronyms=acronym_map,
                    tinyId=getattr(item, 'tinyId', None),
                    field_path=field_path
                )
                for match in matches:
                    catalog.add(match)
                    abbrev_count += 1

        if abbrev_count > 0:
            logger.info(f"Extracted {abbrev_count} abbreviation-only instrument references")

    # Third pass: extract supplementary patterns (non-Title-Case instruments)
    if extract_supplementary:
        supp_count = 0
        for item, text_spans in text_spans_by_item:
            for field_path, text in text_spans:
                matches = extractor.extract_supplementary_patterns(
                    text,
                    tinyId=getattr(item, 'tinyId', None),
                    field_path=field_path
                )
                for match in matches:
                    catalog.add(match)
                    supp_count += 1

        if supp_count > 0:
            logger.info(f"Extracted {supp_count} supplementary pattern references")

    return catalog
