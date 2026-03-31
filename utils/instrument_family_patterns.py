"""
Instrument family detection patterns.

Rule-based pattern matching to assign instruments to known families
(e.g., Neuro-QOL, PROMIS, MDS-UPDRS). Provides high-confidence family
detection for common instrument families, with fallback to LLM adjudication
for uncertain cases.

Usage:
    from utils.instrument_family_patterns import InstrumentFamilyDetector

    detector = InstrumentFamilyDetector()
    family_id, confidence = detector.detect_family("Neuro-QOL Ability to Participate in SRA")
    # Returns: ("neuro-qol", 1.0)
"""

import re
from typing import Tuple, Optional, List, Dict
from dataclasses import dataclass, field


@dataclass
class FamilyPattern:
    """Pattern definition for an instrument family."""
    family_id: str
    display_name: str
    patterns: List[re.Pattern]
    acronym_patterns: List[re.Pattern] = field(default_factory=list)  # Patterns for acronym field
    confidence: float = 1.0  # Base confidence when pattern matches


# Family detection patterns
# Each pattern is case-insensitive and designed to match the instrument name
# (not the full "as part of <instrument>" phrase)

FAMILY_PATTERNS: List[FamilyPattern] = [
    FamilyPattern(
        family_id="neuro-qol",
        display_name="Neuro-QOL",
        patterns=[
            re.compile(r'\bneuro[\-\s]?qol\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="promis",
        display_name="PROMIS",
        patterns=[
            re.compile(r'\bpromis\b', re.IGNORECASE),
            # "outcome" (singular) as used in data, "outcomes" (plural) as sometimes written
            re.compile(r'\bpatient[\-\s]?reported[\-\s]?outcome[s]?[\-\s]?measurement[\-\s]?information[\-\s]?system\b', re.IGNORECASE),
        ],
        acronym_patterns=[
            re.compile(r'^PROMIS$', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="mds-updrs",
        display_name="MDS-UPDRS",
        patterns=[
            re.compile(r'\bmds[\-\s]?updrs\b', re.IGNORECASE),
            re.compile(r'\bmovement\s+disorder\s+society.*unified\s+parkinson', re.IGNORECASE),
            re.compile(r'\bunified\s+parkinson.*disease\s+rating\s+scale\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="sf-health",
        display_name="SF Health Survey",
        patterns=[
            re.compile(r'\bsf[\-\s]?(?:36|12|8|6)\b', re.IGNORECASE),
            re.compile(r'\bshort[\-\s]?form.*health\s+survey\b', re.IGNORECASE),
            re.compile(r'\b\d+[\-\s]?item\s+short[\-\s]?form\b', re.IGNORECASE),
        ],
        acronym_patterns=[
            re.compile(r'^SF[\-]?(?:36|12|8|6)$', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="beck",
        display_name="Beck Inventory",
        patterns=[
            re.compile(r'\bbeck\s+(?:depression|anxiety)\s+inventory\b', re.IGNORECASE),
            re.compile(r'\b(?:bdi|bai)[\-\s]?(?:ii|2)?\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="phq",
        display_name="PHQ",
        patterns=[
            re.compile(r'\bphq[\-\s]?\d*\b', re.IGNORECASE),
            re.compile(r'\bpatient\s+health\s+questionnaire\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="gad",
        display_name="GAD",
        patterns=[
            re.compile(r'\bgad[\-\s]?\d+\b', re.IGNORECASE),
            re.compile(r'\bgeneralized\s+anxiety\s+disorder.*scale\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="mmse",
        display_name="MMSE",
        patterns=[
            re.compile(r'\bmmse\b', re.IGNORECASE),
            re.compile(r'\bmini[\-\s]?mental\s+state\s+examination\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="moca",
        display_name="MoCA",
        patterns=[
            re.compile(r'\bmoca\b', re.IGNORECASE),
            re.compile(r'\bmontreal\s+cognitive\s+assessment\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="nihss",
        display_name="NIHSS",
        patterns=[
            re.compile(r'\bnihss\b', re.IGNORECASE),
            re.compile(r'\bnih\s+stroke\s+scale\b', re.IGNORECASE),
            re.compile(r'\bnational\s+institutes?\s+of\s+health\s+stroke\s+scale\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="pdqualif",
        display_name="PDQUALIF",
        patterns=[
            re.compile(r'\bpdqualif\b', re.IGNORECASE),
            re.compile(r"\bparkinson(?:'?s)?\s+disease\s+quality\s+of\s+life\b", re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="dsq",
        display_name="DSQ",
        patterns=[
            re.compile(r'\bdsq\b', re.IGNORECASE),
            re.compile(r'\bdepaul\s+symptom\s+questionnaire\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="rome",
        display_name="Rome Criteria",
        patterns=[
            re.compile(r'\brome\s+(?:ii|iii|iv|[234])\b', re.IGNORECASE),
            re.compile(r'\brcm\d+\b', re.IGNORECASE),  # RCM3 = Rome III Constipation Module
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="nih-toolbox",
        display_name="NIH Toolbox",
        patterns=[
            re.compile(r'\bnih\s+toolbox\b', re.IGNORECASE),
            re.compile(r'\bnihtoolbox\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    # Quality of Life scales - disease-specific
    FamilyPattern(
        family_id="swal-qol",
        display_name="SWAL-QOL",
        patterns=[
            re.compile(r'\bswal[\-\s]?qol\b', re.IGNORECASE),
            re.compile(r'\bquality\s+of\s+life\s+in\s+swallowing\s+disorders?\b', re.IGNORECASE),
        ],
        acronym_patterns=[
            re.compile(r'^SWAL[\-]?QOL$', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="ms-qol",
        display_name="MS-QOL",
        patterns=[
            re.compile(r'\bms[\-\s]?qol\b', re.IGNORECASE),
            re.compile(r'\bmultiple\s+sclerosis\s+quality\s+of\s+life\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    FamilyPattern(
        family_id="ss-qol",
        display_name="SS-QOL",
        patterns=[
            re.compile(r'\bss[\-\s]?qol\b', re.IGNORECASE),
            re.compile(r'\bstroke\s+specific\s+quality\s+of\s+life\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    # Gambling and addiction instruments
    FamilyPattern(
        family_id="sogs",
        display_name="SOGS",
        patterns=[
            re.compile(r'\bsogs\b', re.IGNORECASE),
            re.compile(r'\bsouth\s+oaks?\s+gambling\s+screen\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    # PhenX toolkit
    FamilyPattern(
        family_id="phenx",
        display_name="PhenX",
        patterns=[
            re.compile(r'\bphenx\b', re.IGNORECASE),
        ],
        acronym_patterns=[
            re.compile(r'^PhenX$', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    # Substance use screening
    FamilyPattern(
        family_id="assist",
        display_name="ASSIST",
        patterns=[
            re.compile(r'\bASSIST\b'),
            re.compile(r'\balcohol\s+smoking\s+and\s+substance\s+use\s+involvement\s+screening\s+test\b', re.IGNORECASE),
        ],
        acronym_patterns=[
            re.compile(r'^ASSIST$', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
    # Visual functioning
    FamilyPattern(
        family_id="nei-vfq",
        display_name="NEI-VFQ",
        patterns=[
            re.compile(r'\bnei[\-\s]?vfq\b', re.IGNORECASE),
            re.compile(r'\bnational\s+eye\s+institute\s+visual\s+functioning\b', re.IGNORECASE),
        ],
        confidence=1.0,
    ),
]


# Hierarchical family prefixes for subinstrument extraction
# Maps family_id to regex pattern matching the family prefix to strip
# The remainder after the prefix is the subinstrument name
HIERARCHICAL_FAMILY_PREFIXES: Dict[str, re.Pattern] = {
    "neuro-qol": re.compile(r'^neuro[\-\s]?qol\s+', re.IGNORECASE),
    "promis": re.compile(r'^promis\s+', re.IGNORECASE),
    "nih-toolbox": re.compile(r'^nih\s+toolbox\s+', re.IGNORECASE),
    "mds-updrs": re.compile(r'^(?:mds[\-\s]?updrs|unified\s+parkinson[\'s]*\s+disease\s+rating\s+scale)\s+', re.IGNORECASE),
}


def extract_subinstrument(instrument_name: str, family_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract subinstrument name and ID from a hierarchical instrument name.

    For families like PROMIS, NIH Toolbox, Neuro-QOL that have multiple subscales,
    extracts the subscale/subinstrument portion after the family prefix.

    Args:
        instrument_name: Full instrument name (e.g., "PROMIS Pain Interference")
        family_id: Detected family ID

    Returns:
        Tuple of (subinstrument_name, subinstrument_id) or (None, None) if not hierarchical
    """
    prefix_pattern = HIERARCHICAL_FAMILY_PREFIXES.get(family_id)
    if not prefix_pattern:
        return None, None

    # Remove the family prefix to get subinstrument name
    subinstrument_name = prefix_pattern.sub('', instrument_name).strip()

    if not subinstrument_name or subinstrument_name.lower() == instrument_name.lower():
        # No subinstrument found or it's the same as the full name
        return None, None

    # Generate subinstrument_id slug
    subinstrument_id = re.sub(r'[^a-z0-9\s]', '', subinstrument_name.lower())
    subinstrument_id = '-'.join(subinstrument_id.split())

    return subinstrument_name, subinstrument_id


# False positive patterns - text that looks like instruments but isn't
FALSE_POSITIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r'\bversion\s+[\d.]+\b', re.IGNORECASE),
    re.compile(r'\boccupational\s+(?:history|exposure)\b', re.IGNORECASE),
    re.compile(r'\bstandardiz(?:e|ation)\s+effort\b', re.IGNORECASE),
    re.compile(r'\b(?:your|their|the)\s+(?:job|work|daily)\b', re.IGNORECASE),
    re.compile(r'\b(?:routine|standard|regular)\s+(?:care|practice|procedure)\b', re.IGNORECASE),
]


def generate_instrument_id(canonical_name: str, family_id: str) -> str:
    """
    Generate a unique instrument_id slug from canonical name and family.

    Args:
        canonical_name: Full instrument name
        family_id: Family identifier

    Returns:
        Normalized slug like "neuro-qol-ability-participate-sra"
    """
    # Normalize: lowercase, remove non-alphanumeric except spaces
    slug = re.sub(r'[^a-z0-9\s]', '', canonical_name.lower())
    # Collapse whitespace and convert to hyphens
    slug = '-'.join(slug.split())
    # Prefix with family if not already present
    if family_id and family_id != "unknown" and family_id != "other":
        if not slug.startswith(family_id):
            slug = f"{family_id}-{slug}"
    # Limit length
    return slug[:80]


class InstrumentFamilyDetector:
    """
    Detects instrument family membership using pattern matching.

    Provides rule-based family detection with confidence scoring.
    Instruments not matching any known pattern receive family_id="other"
    with lower confidence to flag for potential LLM adjudication.
    """

    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize the detector.

        Args:
            confidence_threshold: Minimum confidence for automatic acceptance.
                Below this threshold, instruments are flagged for review.
        """
        self.confidence_threshold = confidence_threshold
        self._patterns = FAMILY_PATTERNS
        self._false_positives = FALSE_POSITIVE_PATTERNS

    def is_false_positive(self, text: str) -> bool:
        """
        Check if text matches known false positive patterns.

        Args:
            text: Text to check (typically the full match including "as part of")

        Returns:
            True if text matches a false positive pattern
        """
        for pattern in self._false_positives:
            if pattern.search(text):
                return True
        return False

    def detect_family(
        self,
        instrument_name: str,
        full_match: Optional[str] = None,
        acronym: Optional[str] = None,
    ) -> Tuple[str, str, float]:
        """
        Detect the family for an instrument name.

        Args:
            instrument_name: Extracted instrument name (Title Case)
            full_match: Optional full matched text for false positive checking
            acronym: Optional acronym (e.g., "SF-36") to check against acronym patterns

        Returns:
            Tuple of (family_id, display_name, confidence)
        """
        # First, try to match by name patterns
        matched_family = None
        for family_pattern in self._patterns:
            for pattern in family_pattern.patterns:
                if pattern.search(instrument_name):
                    matched_family = family_pattern
                    break
            if matched_family:
                break

        # If no name match, try acronym patterns
        if not matched_family and acronym:
            for family_pattern in self._patterns:
                for pattern in family_pattern.acronym_patterns:
                    if pattern.search(acronym):
                        matched_family = family_pattern
                        break
                if matched_family:
                    break

        # If we found a family match, return it (overrides false positive check)
        if matched_family:
            return (
                matched_family.family_id,
                matched_family.display_name,
                matched_family.confidence,
            )

        # No family match - check for false positives in full match
        # (only applies to unrecognized instruments)
        if full_match and self.is_false_positive(full_match):
            return ("unknown", "Unknown", 0.0)

        # No pattern matched - mark as "other" with lower confidence
        # These may be valid instruments but unrecognized families
        return ("other", "Other Instrument", 0.5)

    def detect_and_identify(
        self,
        instrument_name: str,
        full_match: Optional[str] = None,
        acronym: Optional[str] = None,
        instrument_number: Optional[int] = None,
    ) -> Dict:
        """
        Detect family and generate full identification.

        Args:
            instrument_name: Extracted instrument name
            full_match: Optional full matched text
            acronym: Optional acronym (e.g., "SF-36") - also used for family detection
            instrument_number: Optional sequential number for instrument_id generation

        Returns:
            Dict with family_id, family_display_name, instrument_id,
            family_confidence, identification_method, needs_review,
            subinstrument_name, subinstrument_id
        """
        family_id, display_name, confidence = self.detect_family(
            instrument_name, full_match, acronym
        )

        # Generate instrument_id (sequential format if number provided)
        if instrument_number is not None:
            instrument_id = f"instrument_{instrument_number:04d}"
        else:
            # Fallback to slug-based ID (deprecated)
            instrument_id = generate_instrument_id(instrument_name, family_id)

        # Extract subinstrument for hierarchical families
        subinstrument_name, subinstrument_id = extract_subinstrument(
            instrument_name, family_id
        )

        # Flag for review if below threshold
        needs_review = confidence < self.confidence_threshold

        return {
            "family_id": family_id,
            "family_display_name": display_name,
            "instrument_id": instrument_id,
            "family_confidence": confidence,
            "identification_method": "pattern",
            "needs_review": needs_review,
            "subinstrument_name": subinstrument_name,
            "subinstrument_id": subinstrument_id,
        }

    def get_family_info(self, family_id: str) -> Optional[FamilyPattern]:
        """Get pattern info for a family_id."""
        for fp in self._patterns:
            if fp.family_id == family_id:
                return fp
        return None

    @property
    def known_families(self) -> List[str]:
        """List of known family IDs."""
        return [fp.family_id for fp in self._patterns]
