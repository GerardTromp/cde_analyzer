"""
Abbreviation Dictionary — discover, expand, classify, and persist abbreviation resolutions.

Provides a systematic pipeline for resolving abbreviations found in CDE text:
1. Discover: scan corpus for (ABBREV), [TAG], and bare CAPS patterns
2. Expand: find "Full Name (ABBREV)" expansion sentences in definitions
3. Classify: instrument, study, medical_technique, medical_term, english, unknown
4. Persist: TSV dictionary that carries forward across pipeline runs
5. Export: auto-generate verbatim strip patterns from classified entries

Storage layout::

    {dict_dir}/
        abbreviation_dictionary.tsv    # persistent dictionary

    config/
        abbreviation_dictionary.tsv    # reference dictionary (ships with codebase)
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class AbbreviationEntry:
    """A single abbreviation with its expansion and classification."""
    abbreviation: str              # Short form: "PHQ", "BFI", "PROMIS"
    expansion: str = ""            # Full form: "Patient Health Questionnaire"
    category: str = "unknown"      # instrument|study|medical_technique|medical_term|english|unknown
    confidence: float = 0.0        # 0.0-1.0
    source: str = ""               # parenthetical|bracketed|bare_caps|intercaps|instrument_catalog|manual
    tinyIds: Set[str] = field(default_factory=set)
    n_tinyIds: int = 0
    aliases: str = ""              # Pipe-separated: "PHQ-9|PHQ-15"
    decided_at: str = ""
    notes: str = ""
    decision: str = ""             # strip|skip|tentative_strip|tentative_skip|"" (empty=undecided)


DICTIONARY_TSV_HEADERS = [
    "abbreviation", "expansion", "category", "confidence", "source",
    "tinyIds", "n_tinyIds", "aliases", "decided_at", "notes", "decision",
]

# Category → tentative decision mapping for auto-populated entries
_TENTATIVE_DECISION = {
    "instrument": "tentative_strip",
    "study": "tentative_strip",
    "medical_technique": "tentative_skip",
    "medical_term": "tentative_skip",
    "english": "tentative_skip",
    "unknown": "",
}

VALID_CATEGORIES = {
    "instrument", "study", "medical_technique",
    "medical_term", "english", "unknown",
}

# Words in an expansion that signal instrument classification
INSTRUMENT_WORDS = {
    "questionnaire", "scale", "inventory", "index", "checklist",
    "assessment", "survey", "test", "battery", "measure", "screening",
    "rating", "schedule", "interview", "examination",
    # Extended instrument signals
    "score", "scoring", "evaluation", "screen", "disorders",
    "diagnostic", "symptom", "behavior", "functioning",
    "impairment", "disability", "quality of life",
}

# Words that signal study/trial classification
STUDY_WORDS = {
    "study", "trial", "project", "cohort", "consortium", "initiative",
    "program", "registry", "network", "longitudinal",
}

# Words that signal medical technique / procedure (not a scored instrument)
MEDICAL_TECHNIQUE_WORDS = {
    "electroencephalography", "tomography", "spectroscopy", "imaging",
    "resonance", "ultrasound", "biopsy", "stimulation", "infusion",
    "catheter", "microscopy", "angiography", "echocardiography",
}

# Category for external lookup result
EXTERNAL_LOOKUP_CATEGORIES = {
    "instrument", "study", "medical_technique", "medical_term",
    "english", "organization",
}

# Regex for parenthetical abbreviation: "Full Name (ABBREV)"
# Captures text before (ABBREV) using a possessive-style approach:
# [^(] ensures no nested quantifier backtracking (linear time).
# acronym_align() then trims to the correct expansion boundary.
_PAREN_RE = re.compile(
    r'([^(]{3,200})'                          # text before ( — no backtracking risk
    r'\(([A-Z][A-Z0-9](?:[A-Z0-9\-]*[A-Z0-9])?)\)'  # (ABBREV)
)

# Filler words typically skipped in acronyms
_FILLER_WORDS = frozenset({
    "of", "the", "and", "in", "for", "on", "to", "or", "a", "an",
    "with", "by", "de", "des", "du", "von",
})

# Regex for bracketed tag at end of field
_BRACKET_RE = re.compile(r'\[([A-Z][A-Za-z0-9 .\-/]+)\]\s*$')

# Regex for bare ALL-CAPS at end of field (2+ chars)
_BARE_CAPS_RE = re.compile(r'\b([A-Z][A-Z0-9\-]{1,})\s*$')

# Regex for InterCaps / medial capitals
_INTERCAPS_RE = re.compile(r'\b([a-zA-Z]*[a-z][A-Z][a-zA-Z]*)\b')

# Known LOINC unit/metadata tags that are NOT instruments
_UNIT_TAGS = frozenset({
    "Moles/volume", "Mass/volume", "Mass/Vol", "Molar ratio", "Moles/Vol",
    "Presence", "#", "Identifier", "Reported", "Reported.PHQ",
    "Location", "Type", "Anatomy", "Score", "Length", "Volume", "Mass",
    "Ratio", "Inverse Length", "Date/time", "Units/volume", "Next-of-kin",
    "Interpretation", "Text", "Catalytic activity/Vol", "Percentile",
    "Log Inverse Percent", "Entitic mass", "Entitic volume", "Entitic vol",
    "Clock time", "Mass Ratio", "Time", "ID", "Stated", "Catalytic fraction",
    "Volume Fraction", "Volume fraction", "Mass/mass", "Mass/Mass",
    "Mass fraction difference", "Interp", "Date", "DateRange", "Address",
    "Dosage", "Enzymatic activity/volume", "Retinal digital photography",
    "CMS Assessment",
})


# ---------------------------------------------------------------------------
# AbbreviationDictionary
# ---------------------------------------------------------------------------

class AbbreviationDictionary:
    """Persistent abbreviation dictionary with discovery and classification."""

    def __init__(self, dict_path: Optional[str] = None):
        self.entries: Dict[str, AbbreviationEntry] = {}
        self.dict_path = dict_path

    # -- persistence --------------------------------------------------------

    def load(self, path: Optional[str] = None) -> bool:
        """Load dictionary from TSV. Returns True if file existed."""
        p = Path(path or self.dict_path)
        if not p.exists():
            return False
        with open(p, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                abbrev = row.get("abbreviation", "").strip()
                if not abbrev:
                    continue
                tinyids_str = row.get("tinyIds", "")
                tinyids = set(t for t in re.split(r"[\s|]+", tinyids_str) if t)
                self.entries[abbrev] = AbbreviationEntry(
                    abbreviation=abbrev,
                    expansion=row.get("expansion", ""),
                    category=row.get("category", "unknown"),
                    confidence=float(row.get("confidence", 0)),
                    source=row.get("source", ""),
                    tinyIds=tinyids,
                    n_tinyIds=len(tinyids),
                    aliases=row.get("aliases", ""),
                    decided_at=row.get("decided_at", ""),
                    notes=row.get("notes", ""),
                    decision=row.get("decision", ""),
                )
        return True

    def save(self, path: Optional[str] = None) -> None:
        """Write dictionary to TSV."""
        p = Path(path or self.dict_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=DICTIONARY_TSV_HEADERS,
                delimiter="\t", lineterminator="\n", extrasaction="ignore",
            )
            writer.writeheader()
            for abbrev in sorted(self.entries):
                e = self.entries[abbrev]
                # Firm decisions are preserved; empty decisions get tentative auto-fill
                decision = e.decision
                if not decision:
                    decision = _TENTATIVE_DECISION.get(e.category, "")
                writer.writerow({
                    "abbreviation": e.abbreviation,
                    "expansion": e.expansion,
                    "category": e.category,
                    "confidence": f"{e.confidence:.2f}",
                    "source": e.source,
                    "tinyIds": " ".join(sorted(e.tinyIds)),
                    "n_tinyIds": len(e.tinyIds),
                    "aliases": e.aliases,
                    "decided_at": e.decided_at,
                    "notes": e.notes,
                    "decision": decision,
                })

    def merge(
        self, other: "AbbreviationDictionary",
        growth_factor: float = 3.0,
        permanent_skips: Optional[Set[str]] = None,
    ) -> Dict[str, int]:
        """Merge other into self. Other overwrites on conflict.

        Args:
            growth_factor: When a "skip" entry's tinyId count grows by this
                factor or more, demote it to "tentative_skip" for re-review.
                Set to 0 to disable. Default: 3.0.
            permanent_skips: Set of abbreviation strings exempt from k-fold
                re-evaluation (domain constants that should never be reviewed).

        Returns:
            Dict with counts: added, updated, unchanged, flagged_for_review.
        """
        added = updated = unchanged = flagged = 0
        if permanent_skips is None:
            permanent_skips = set()
        for abbrev, entry in other.entries.items():
            if abbrev not in self.entries:
                self.entries[abbrev] = entry
                added += 1
            elif entry.decided_at > self.entries[abbrev].decided_at:
                self.entries[abbrev] = entry
                updated += 1
            else:
                existing = self.entries[abbrev]
                # k-fold re-evaluation: if skip decision + significant growth
                if (growth_factor > 0
                        and existing.decision == "skip"
                        and abbrev not in permanent_skips
                        and existing.n_tinyIds > 0
                        and len(entry.tinyIds) >= growth_factor * existing.n_tinyIds):
                    existing.decision = "tentative_skip"
                    existing.tinyIds = entry.tinyIds
                    existing.n_tinyIds = len(entry.tinyIds)
                    existing.notes = (
                        f"{existing.notes}; "
                        f"FLAGGED: tinyId growth {existing.n_tinyIds}→"
                        f"{len(entry.tinyIds)} (>={growth_factor}x)"
                    ).lstrip("; ")
                    flagged += 1
                else:
                    # Update tinyIds from new corpus without changing decision
                    if entry.tinyIds:
                        existing.tinyIds = entry.tinyIds
                        existing.n_tinyIds = len(entry.tinyIds)
                    unchanged += 1
        return {
            "added": added, "updated": updated,
            "unchanged": unchanged, "flagged_for_review": flagged,
        }

    # -- discovery ----------------------------------------------------------

    def discover_parenthetical(
        self, data: List[dict], field_paths: Optional[List[str]] = None,
    ) -> int:
        """Find "Full Name (ABBREV)" patterns in definitions. Returns count."""
        if field_paths is None:
            field_paths = ["definitions.*.definition"]

        count = 0
        for record in data:
            tinyid = record.get("tinyId", "")
            for fp in field_paths:
                for text in _extract_texts(record, fp.split(".")):
                    for m in _PAREN_RE.finditer(text):
                        raw_expansion = m.group(1).strip()
                        abbrev = m.group(2).strip()
                        # Acronym-align: trim to the correct boundary
                        expansion = acronym_align(raw_expansion, abbrev)
                        # Strip leading articles
                        expansion = re.sub(
                            r'^(?:The|the|A|a|An|an)\s+', '', expansion,
                        )
                        if len(abbrev) < 2:
                            continue
                        if abbrev not in self.entries:
                            self.entries[abbrev] = AbbreviationEntry(
                                abbreviation=abbrev,
                                expansion=expansion,
                                source="parenthetical",
                                confidence=0.95,
                            )
                            count += 1
                        entry = self.entries[abbrev]
                        entry.tinyIds.add(tinyid)
                        entry.n_tinyIds = len(entry.tinyIds)
                        if not entry.expansion and expansion:
                            entry.expansion = expansion
        return count

    def discover_bracketed(
        self, data: List[dict], field_paths: Optional[List[str]] = None,
    ) -> int:
        """Find [TAG] at end of designations/definitions. Returns count."""
        if field_paths is None:
            field_paths = [
                "definitions.*.definition",
                "designations.*.designation",
            ]

        count = 0
        for record in data:
            tinyid = record.get("tinyId", "")
            for fp in field_paths:
                for text in _extract_texts(record, fp.split(".")):
                    m = _BRACKET_RE.search(text)
                    if not m:
                        continue
                    tag = m.group(1).strip()
                    if tag in _UNIT_TAGS:
                        continue
                    key = f"[{tag}]"
                    if key not in self.entries:
                        self.entries[key] = AbbreviationEntry(
                            abbreviation=key,
                            source="bracketed",
                            confidence=0.85,
                        )
                        count += 1
                    entry = self.entries[key]
                    entry.tinyIds.add(tinyid)
                    entry.n_tinyIds = len(entry.tinyIds)
        return count

    def discover_bare_caps(
        self, data: List[dict], field_paths: Optional[List[str]] = None,
        english_words: Optional[Set[str]] = None,
    ) -> int:
        """Find trailing ALL-CAPS tokens in designations. Returns count.

        Skips fields where all tokens are uppercase (the field is "shouting",
        not using abbreviation conventions). A single all-caps token as the
        entire field IS treated as a legitimate abbreviation.
        """
        if field_paths is None:
            field_paths = ["designations.*.designation"]

        count = 0
        for record in data:
            tinyid = record.get("tinyId", "")
            for fp in field_paths:
                for text in _extract_texts(record, fp.split(".")):
                    stripped = text.strip()
                    # Skip all-caps fields with 2+ tokens (shouting)
                    tokens = stripped.split()
                    if len(tokens) >= 2 and all(
                        t.isupper() for t in tokens if t.isalpha()
                    ):
                        continue
                    m = _BARE_CAPS_RE.search(stripped)
                    if not m:
                        continue
                    token = m.group(1).strip()
                    if len(token) < 2:
                        continue
                    # Filter English words
                    if english_words and token.lower() in english_words:
                        continue
                    if token not in self.entries:
                        self.entries[token] = AbbreviationEntry(
                            abbreviation=token,
                            source="bare_caps",
                            confidence=0.5,
                        )
                        count += 1
                    entry = self.entries[token]
                    entry.tinyIds.add(tinyid)
                    entry.n_tinyIds = len(entry.tinyIds)
        return count

    def discover_intercaps(
        self, data: List[dict], field_paths: Optional[List[str]] = None,
    ) -> int:
        """Find InterCaps/medial capital tokens. Returns count."""
        if field_paths is None:
            field_paths = ["designations.*.designation"]

        count = 0
        for record in data:
            tinyid = record.get("tinyId", "")
            for fp in field_paths:
                for text in _extract_texts(record, fp.split(".")):
                    for m in _INTERCAPS_RE.finditer(text):
                        token = m.group(1).strip()
                        if len(token) < 3:
                            continue
                        # Skip common patterns: pH, mL, etc.
                        if token in ("pH", "mL", "dL", "mg", "kg", "mmHg"):
                            continue
                        if token not in self.entries:
                            self.entries[token] = AbbreviationEntry(
                                abbreviation=token,
                                source="intercaps",
                                category="medical_term",
                                confidence=0.7,
                            )
                            count += 1
                        entry = self.entries[token]
                        entry.tinyIds.add(tinyid)
                        entry.n_tinyIds = len(entry.tinyIds)
        return count

    # -- expansion ----------------------------------------------------------

    def expand_from_context(
        self, data: List[dict], field_paths: Optional[List[str]] = None,
    ) -> int:
        """Search definitions for expansion sentences matching unexpanded entries."""
        if field_paths is None:
            field_paths = ["definitions.*.definition"]

        # Build tinyId → text index
        tid_texts: Dict[str, List[str]] = {}
        for record in data:
            tid = record.get("tinyId", "")
            texts = []
            for fp in field_paths:
                texts.extend(_extract_texts(record, fp.split(".")))
            if texts:
                tid_texts[tid] = texts

        expanded = 0
        for abbrev, entry in self.entries.items():
            if entry.expansion:
                continue
            # Strip brackets for matching
            clean = abbrev.strip("[]")
            if len(clean) < 2:
                continue
            # Search definitions of CDEs where this abbreviation appears
            for tid in entry.tinyIds:
                if tid not in tid_texts:
                    continue
                for text in tid_texts[tid]:
                    # Look for "Expansion (ABBREV)" or "Expansion [ABBREV]"
                    pat = re.compile(
                        r'((?:[A-Z][a-zA-Z\']+\s+){1,8}[A-Z][a-zA-Z\']+)\s*'
                        r'[\(\[]' + re.escape(clean) + r'[\)\]]',
                    )
                    m = pat.search(text)
                    if m:
                        entry.expansion = m.group(1).strip()
                        if entry.confidence < 0.9:
                            entry.confidence = 0.9
                        expanded += 1
                        break
                if entry.expansion:
                    break
        return expanded

    def expand_from_catalog(
        self, acronym_map: Dict[str, str],
    ) -> int:
        """Fill expansions from an acronym→name mapping (e.g., InstrumentCatalog)."""
        expanded = 0
        for abbrev, entry in self.entries.items():
            if entry.expansion:
                continue
            clean = abbrev.strip("[]")
            if clean in acronym_map:
                entry.expansion = acronym_map[clean]
                entry.source = entry.source or "instrument_catalog"
                if entry.confidence < 0.85:
                    entry.confidence = 0.85
                expanded += 1
        return expanded

    # -- classification -----------------------------------------------------

    def classify_by_heuristic(self) -> int:
        """Apply word-based heuristics to classify entries. Returns count classified."""
        classified = 0
        for entry in self.entries.values():
            if entry.category != "unknown":
                continue
            if not entry.expansion:
                continue

            exp_lower = entry.expansion.lower()
            words = set(exp_lower.split())

            # Check multi-word phrases too
            is_instrument = bool(words & INSTRUMENT_WORDS)
            if not is_instrument:
                is_instrument = "quality of life" in exp_lower
            is_study = bool(words & STUDY_WORDS)
            is_medical_tech = bool(words & MEDICAL_TECHNIQUE_WORDS)

            if is_medical_tech and not is_instrument:
                entry.category = "medical_technique"
                entry.confidence = max(entry.confidence, 0.85)
                classified += 1
            elif is_instrument and not is_study:
                entry.category = "instrument"
                entry.confidence = max(entry.confidence, 0.9)
                classified += 1
            elif is_study and not is_instrument:
                entry.category = "study"
                entry.confidence = max(entry.confidence, 0.85)
                classified += 1
            elif is_instrument and is_study:
                # Both signals — instrument takes precedence
                entry.category = "instrument"
                entry.confidence = max(entry.confidence, 0.8)
                classified += 1

        return classified

    def classify_by_external_results(
        self, lookup_results: Dict[str, Dict[str, Any]],
    ) -> int:
        """Apply external lookup results to classify entries.

        Parameters
        ----------
        lookup_results : dict
            Mapping: abbreviation → {"category": str, "confidence": float,
            "expansion": str (optional), "notes": str (optional)}

        Returns count of entries classified.
        """
        classified = 0
        for abbrev, result in lookup_results.items():
            # Match both bare and bracketed forms
            entry = self.entries.get(abbrev)
            if not entry:
                entry = self.entries.get(f"[{abbrev}]")
            if not entry:
                continue
            if entry.category != "unknown":
                continue

            category = result.get("category", "")
            if category not in VALID_CATEGORIES:
                continue

            entry.category = category
            confidence = result.get("confidence", 0.75)
            entry.confidence = max(entry.confidence, confidence)
            if result.get("expansion") and not entry.expansion:
                entry.expansion = result["expansion"]
            if result.get("notes"):
                entry.notes = (entry.notes + "; " if entry.notes else "") + result["notes"]
            entry.source = entry.source or "external_lookup"
            classified += 1

        return classified

    def classify_by_family_detector(
        self, family_patterns: List,
    ) -> int:
        """Classify entries matching known InstrumentFamilyDetector patterns."""
        classified = 0
        for entry in self.entries.values():
            text = entry.expansion or entry.abbreviation.strip("[]")
            for fp in family_patterns:
                for pat in fp.patterns:
                    if pat.search(text):
                        entry.category = "instrument"
                        entry.confidence = max(entry.confidence, fp.confidence)
                        if not entry.notes:
                            entry.notes = f"Family: {fp.display_name}"
                        classified += 1
                        break
                else:
                    for pat in fp.acronym_patterns:
                        if pat.search(text):
                            entry.category = "instrument"
                            entry.confidence = max(entry.confidence, fp.confidence)
                            if not entry.notes:
                                entry.notes = f"Family: {fp.display_name}"
                            classified += 1
                            break
                    else:
                        continue
                break
        return classified

    # -- export -------------------------------------------------------------

    def _should_strip(self, entry: AbbreviationEntry,
                      categories: List[str]) -> bool:
        """Check if entry should produce strip patterns.

        If the entry has a firm decision, use it. Otherwise fall back to
        category membership.
        """
        dec = (entry.decision or "").replace("tentative_", "")
        if dec == "strip":
            return True
        if dec == "skip":
            return False
        # No decision — fall back to category
        return entry.category in categories

    def export_strip_patterns(
        self, output_path: str,
        categories: Optional[List[str]] = None,
    ) -> int:
        """Generate verbatim strip patterns YAML from classified entries."""
        if categories is None:
            categories = ["instrument", "study"]

        entries = [e for e in self.entries.values()
                   if self._should_strip(e, categories)]
        entries.sort(key=lambda e: (-e.n_tinyIds, e.abbreviation))

        lines = [
            "# Auto-generated from abbreviation dictionary",
            f"# Generated: {datetime.now().isoformat()}",
            f"# Entries: {len(entries)}",
            "",
            "abbreviation_dictionary:",
        ]

        for entry in entries:
            abbrev = entry.abbreviation
            if abbrev.startswith("[") and abbrev.endswith("]"):
                # Bracketed: add [TAG] pattern
                lines.append(f'  - pattern: "{abbrev}"')
                lines.append(f'    note: "{entry.expansion or abbrev} - {entry.n_tinyIds} CDEs ({entry.category})"')
                lines.append("")
            else:
                # Bare: add as-is
                lines.append(f'  - pattern: "{abbrev}"')
                lines.append(f'    note: "{entry.expansion or abbrev} - {entry.n_tinyIds} CDEs ({entry.category})"')
                lines.append("")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return len(entries)

    def export_scoped_patterns(
        self, output_path: str,
        categories: Optional[List[str]] = None,
    ) -> int:
        """Generate tinyId-scoped TSV for bare abbreviation stripping."""
        if categories is None:
            categories = ["instrument", "study"]

        entries = [
            e for e in self.entries.values()
            if self._should_strip(e, categories)
            and not e.abbreviation.startswith("[")
            and e.tinyIds
        ]
        entries.sort(key=lambda e: (-e.n_tinyIds, e.abbreviation))

        cols = ["pattern", "tinyIds", "tinyid_count", "note"]
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=cols, delimiter="\t",
                lineterminator="\n", extrasaction="ignore",
            )
            writer.writeheader()
            for e in entries:
                writer.writerow({
                    "pattern": e.abbreviation,
                    "tinyIds": " ".join(sorted(e.tinyIds)),
                    "tinyid_count": len(e.tinyIds),
                    "note": e.expansion or e.abbreviation,
                })
        return len(entries)

    def export_needs_review(self, output_path: str, threshold: float = 0.8) -> int:
        """Export entries below confidence threshold for human review.

        Excludes zero-tinyId entries (already-resolved manual/seeded entries).
        Pre-fills tentative decisions based on category classification.
        """
        entries = [
            e for e in self.entries.values()
            if (e.confidence < threshold or e.category == "unknown")
            and len(e.tinyIds) > 0  # exclude already-resolved manual entries
            and e.decision not in ("strip", "skip")  # firm decisions don't need review
        ]
        entries.sort(key=lambda e: (-e.n_tinyIds, e.abbreviation))

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=DICTIONARY_TSV_HEADERS, delimiter="\t",
                lineterminator="\n", extrasaction="ignore",
            )
            writer.writeheader()
            for e in entries:
                decision = e.decision
                if not decision:
                    decision = _TENTATIVE_DECISION.get(e.category, "")
                writer.writerow({
                    "abbreviation": e.abbreviation,
                    "expansion": e.expansion,
                    "category": e.category,
                    "confidence": f"{e.confidence:.2f}",
                    "source": e.source,
                    "tinyIds": " ".join(sorted(e.tinyIds)),
                    "n_tinyIds": len(e.tinyIds),
                    "aliases": e.aliases,
                    "decided_at": e.decided_at,
                    "notes": e.notes,
                    "decision": decision,
                })
        return len(entries)

    # -- queries ------------------------------------------------------------

    def lookup(self, abbreviation: str) -> Optional[AbbreviationEntry]:
        return self.entries.get(abbreviation)

    def by_category(self, category: str) -> List[AbbreviationEntry]:
        return [e for e in self.entries.values() if e.category == category]

    def unclassified(self) -> List[AbbreviationEntry]:
        return [e for e in self.entries.values() if e.category == "unknown"]

    def summary(self) -> Dict[str, int]:
        """Return category counts."""
        counts: Dict[str, int] = {}
        for e in self.entries.values():
            counts[e.category] = counts.get(e.category, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Acronym-alignment heuristic
# ---------------------------------------------------------------------------

def acronym_align(text: str, abbreviation: str) -> str:
    """Trim captured expansion text to the acronym-aligned boundary.

    Each letter in the abbreviation should map to the initial letter(s) of
    a token in the expansion. Filler words (of, the, and, ...) are skipped.
    Hyphenated compounds contribute initials per segment (Epstein-Barr → EB).

    Strategy: try every possible starting token, scan left-to-right consuming
    abbreviation letters. Pick the rightmost (latest) start that aligns all
    letters — this trims the most preamble.

    Args:
        text: Broadly captured expansion text (may include preamble).
        abbreviation: The acronym, e.g. "CARDIA", "EBV", "SSI".

    Returns:
        Trimmed expansion aligned to the abbreviation letters.
        Falls back to original text if alignment fails.
    """
    # Strip digits and hyphens from abbreviation to get the letters to match
    abbrev_letters = [c.upper() for c in abbreviation if c.isalpha()]
    if not abbrev_letters:
        return text.strip()

    # Tokenize: split on whitespace, then split hyphenated parts
    raw_tokens = text.strip().split()
    # Build list of (token_text, [initial_letters], is_filler) tuples
    # Filler words (of, the, in, ...) CAN contribute initials when the
    # abbreviation includes them (e.g., CARDIA: ...Development In...)
    # but are not required to match.
    token_info: list = []  # [(original_token, [initials], is_filler)]
    for tok in raw_tokens:
        clean = tok.strip(" ,;:")
        if not clean:
            continue
        is_filler = clean.lower() in _FILLER_WORDS
        # Split on hyphens and slashes for multi-segment initials
        segments = re.split(r'[-/]', clean)
        initials = [s[0].upper() for s in segments if s and s[0].isalpha()]
        token_info.append((tok, initials, is_filler))

    def _try_align_from(start: int) -> bool:
        """Try to consume all abbrev_letters starting from token index start."""
        ai = 0
        for ti in range(start, len(token_info)):
            _tok_text, initials, _is_filler = token_info[ti]
            for ini in initials:
                if ai < len(abbrev_letters) and ini == abbrev_letters[ai]:
                    ai += 1
            if ai >= len(abbrev_letters):
                return True
        return ai >= len(abbrev_letters)

    # Try each starting position, prefer the rightmost (most trimmed) success
    best_start = None
    for start in range(len(token_info)):
        if _try_align_from(start):
            best_start = start

    if best_start is None:
        return text.strip()

    # Reconstruct from best_start onward, but skip leading filler words
    # (e.g., if the rightmost alignment starts at "the Coronary...",
    # we want "Coronary..." not "the Coronary...")
    actual_start = best_start
    while actual_start < len(token_info) and token_info[actual_start][2]:
        actual_start += 1
    if actual_start >= len(token_info):
        actual_start = best_start  # safety: don't skip everything
    aligned_tokens = [info[0] for info in token_info[actual_start:]]
    result = " ".join(aligned_tokens).strip(" ,;:")
    return result if result else text.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_texts(obj: Any, parts: List[str]) -> List[str]:
    """Navigate nested dict/list to extract text values at a dot-separated path."""
    if not parts:
        return [obj] if isinstance(obj, str) else []
    key = parts[0]
    rest = parts[1:]
    if key == "*" and isinstance(obj, list):
        result = []
        for item in obj:
            result.extend(_extract_texts(item, rest))
        return result
    if isinstance(obj, dict) and key in obj:
        return _extract_texts(obj[key], rest)
    return []
