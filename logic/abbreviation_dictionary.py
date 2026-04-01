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


DICTIONARY_TSV_HEADERS = [
    "abbreviation", "expansion", "category", "confidence", "source",
    "tinyIds", "n_tinyIds", "aliases", "decided_at", "notes",
]

VALID_CATEGORIES = {
    "instrument", "study", "medical_technique",
    "medical_term", "english", "unknown",
}

# Words in an expansion that signal instrument classification
INSTRUMENT_WORDS = {
    "questionnaire", "scale", "inventory", "index", "checklist",
    "assessment", "survey", "test", "battery", "measure", "screening",
    "rating", "schedule", "interview", "examination",
}

# Words that signal study/trial classification
STUDY_WORDS = {
    "study", "trial", "project", "cohort", "consortium", "initiative",
    "program", "registry", "network",
}

# Regex for parenthetical abbreviation: "Full Name (ABBREV)"
_PAREN_RE = re.compile(
    r'((?:[A-Z][a-zA-Z\']+(?:\s+(?:of|the|and|in|for|on|to|or|a|an|with|by)\s+)?'
    r'(?:[A-Z]?[a-zA-Z\']+\s+)*)'       # title-case expansion words
    r'(?:[A-Z][a-zA-Z\']+))'             # last word
    r'\s*'
    r'\(([A-Z][A-Z0-9](?:[A-Z0-9\-]*[A-Z0-9])?)\)'  # (ABBREV)
)

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
                })

    def merge(self, other: "AbbreviationDictionary") -> Dict[str, int]:
        """Merge other into self. Other overwrites on conflict. Returns counts."""
        added = updated = unchanged = 0
        for abbrev, entry in other.entries.items():
            if abbrev not in self.entries:
                self.entries[abbrev] = entry
                added += 1
            elif entry.decided_at > self.entries[abbrev].decided_at:
                self.entries[abbrev] = entry
                updated += 1
            else:
                unchanged += 1
        return {"added": added, "updated": updated, "unchanged": unchanged}

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
                        expansion = m.group(1).strip()
                        # Strip leading articles
                        expansion = re.sub(
                            r'^(?:The|the|A|a|An|an)\s+', '', expansion,
                        )
                        abbrev = m.group(2).strip()
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
        """Find trailing ALL-CAPS tokens in designations. Returns count."""
        if field_paths is None:
            field_paths = ["designations.*.designation"]

        count = 0
        for record in data:
            tinyid = record.get("tinyId", "")
            for fp in field_paths:
                for text in _extract_texts(record, fp.split(".")):
                    m = _BARE_CAPS_RE.search(text.strip())
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

            words = set(entry.expansion.lower().split())
            is_instrument = bool(words & INSTRUMENT_WORDS)
            is_study = bool(words & STUDY_WORDS)

            if is_instrument and not is_study:
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

    def export_strip_patterns(
        self, output_path: str,
        categories: Optional[List[str]] = None,
    ) -> int:
        """Generate verbatim strip patterns YAML from classified entries."""
        if categories is None:
            categories = ["instrument", "study"]

        entries = [e for e in self.entries.values() if e.category in categories]
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
            if e.category in categories
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
        """Export entries below confidence threshold for human review."""
        entries = [
            e for e in self.entries.values()
            if e.confidence < threshold or e.category == "unknown"
        ]
        entries.sort(key=lambda e: (-e.n_tinyIds, e.abbreviation))

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cols = DICTIONARY_TSV_HEADERS + ["decision"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=cols, delimiter="\t",
                lineterminator="\n", extrasaction="ignore",
            )
            writer.writeheader()
            for e in entries:
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
                    "decision": "",
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
