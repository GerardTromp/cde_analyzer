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
"""

import re
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict


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
    instrument_id: Optional[str] = None     # e.g., "neuro-qol-ability-participate-sra"
    family_confidence: Optional[float] = None  # 0.0-1.0 confidence in family assignment
    identification_method: Optional[str] = None  # "pattern", "llm", "manual"
    needs_review: bool = False              # True if confidence < threshold


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

    def assign_families(self, confidence_threshold: float = 0.7) -> None:
        """
        Assign family identification to all instruments using pattern detection.

        Args:
            confidence_threshold: Minimum confidence for automatic acceptance.
                Below this threshold, instruments are flagged for review.
        """
        from utils.instrument_family_patterns import InstrumentFamilyDetector

        detector = InstrumentFamilyDetector(confidence_threshold=confidence_threshold)

        for matches in self.instruments.values():
            for match in matches:
                # Detect family and generate identification
                result = detector.detect_and_identify(
                    instrument_name=match.instrument_name,
                    full_match=match.full_match,
                    acronym=match.acronym,
                )
                # Populate family fields
                match.family_id = result["family_id"]
                match.family_display_name = result["family_display_name"]
                match.instrument_id = result["instrument_id"]
                match.family_confidence = result["family_confidence"]
                match.identification_method = result["identification_method"]
                match.needs_review = result["needs_review"]

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
    - "as part of the Drug Abuse Screening Test (DAST)"
    - "as part of version 1.0 of 36-item Short Form Health Survey (SF-36)"
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
    TITLE_CASE_WORD = r'[A-Z][a-z0-9]*(?:-[A-Za-z][a-z0-9]*)*'

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
    INSTRUMENT_NAME = rf'({INSTRUMENT_START}(?:\s+{INSTRUMENT_WORD})+)'

    # Optional acronym in parentheses: (SF-36), (DAST), (PHQ-9), (K-SADS-PL)
    # Allows multiple hyphenated segments for complex acronyms
    ACRONYM_PATTERN = r'(?:\s*\(([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)\))?'

    # Full pattern: case-insensitive for "as part of", case-sensitive for instrument name
    # Use character classes to handle case variations in "as part of"
    FULL_PATTERN = re.compile(
        r'[Aa][Ss]\s+[Pp][Aa][Rr][Tt]\s+[Oo][Ff]\s+' +  # Case-insensitive "as part of"
        VERSION_PATTERN +
        ARTICLE_PATTERN +
        NUMBERED_PREFIX +
        INSTRUMENT_NAME +
        ACRONYM_PATTERN
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
    min_name_words: int = 3
) -> InstrumentCatalog:
    """
    Extract instruments from a list of CDE items.

    Convenience function for batch processing.

    Args:
        items: List of CDEItem objects
        field_names: Field names to extract from
        min_name_words: Minimum words in instrument name

    Returns:
        InstrumentCatalog with all detected instruments
    """
    from utils.field_extractor import extract_field_texts

    extractor = InstrumentExtractor(min_name_words=min_name_words)
    catalog = InstrumentCatalog()

    for item in items:
        text_spans = extract_field_texts(item, field_names)
        for field_path, text in text_spans:
            matches = extractor.extract_from_text(
                text,
                tinyId=getattr(item, 'tinyId', None),
                field_path=field_path
            )
            for match in matches:
                catalog.add(match)

    return catalog
