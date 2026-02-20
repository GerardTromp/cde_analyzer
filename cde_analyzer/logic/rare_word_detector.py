"""
Rare word detection for CDE text fields.

Identifies single words (unigrams) that appear across many CDEs but are rare
in general English.  These words — typically domain acronyms, invented terms,
and mixed-case contractions (PhenX, MedDRA, NIHSS) — produce distinctive
embedding vectors because language models fall back to sub-word tokenisation.
Stripping them before embedding prevents artificial clustering artifacts.

Algorithm:
    1. Tokenise all CDE field texts into words (whitespace + punctuation split).
    2. For each unique word form, count distinct tinyIds it appears in.
    3. Look up Zipf frequency in general English via ``wordfreq``.
    4. Apply an all-caps penalty (ALL-CAPS words that spell common English
       are likely acronyms in CDE context, not the common word).
    5. Flag words whose *effective* Zipf score falls below a threshold
       AND that appear in >= min_tinyids CDEs.

Output is a list of ``RareWord`` dataclass instances, ready for TSV export.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────

@dataclass
class RareWordConfig:
    """Tuning knobs for the rare-word detector."""

    zipf_threshold: float = 1.5
    """Maximum effective Zipf score to be considered *rare*."""

    caps_penalty: float = 2.5
    """Zipf penalty applied to ALL-CAPS words (len >= 2).
    Rationale: ``TOAST`` as an acronym ≠ ``toast`` the food.
    ``wordfreq`` lowercases internally, so the raw score conflates them."""

    min_tinyids: int = 3
    """Minimum distinct CDEs a word must appear in to be reported."""

    min_word_len: int = 2
    """Ignore single-character tokens (articles, list bullets, etc.)."""

    field_names: List[str] = field(
        default_factory=lambda: ["definitions.*.definition",
                                 "designations.*.designation"]
    )
    """Field paths to scan."""

    exclude_patterns: Optional[Set[str]] = None
    """Words already covered by instrument/phrase patterns — skip them."""


# ──────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────

@dataclass
class RareWord:
    """One detected rare word with its metadata."""
    word: str                   # Verbatim form as it appears in CDE text
    cde_count: int              # Distinct tinyIds containing this word
    raw_zipf: float             # wordfreq Zipf score (lowercase lookup)
    effective_zipf: float       # After caps penalty
    is_allcaps: bool            # Whether the dominant form is ALL-CAPS
    field_profile: str          # "def", "desig", "def+desig"
    tinyids: Set[str]           # All tinyIds containing the word
    example_contexts: List[str] # Short surrounding-text snippets (for curation)


# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────

# Split on whitespace and common punctuation boundaries, keeping
# only "word-like" tokens (letters, digits, hyphens).
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*[A-Za-z0-9]|[A-Za-z]")


def compute_effective_zipf(
    word: str,
    raw_zipf: float,
    caps_penalty: float,
) -> Tuple[float, bool]:
    """Return (effective_zipf, is_allcaps) for *word*."""
    is_caps = word.isupper() and len(word) >= 2
    if is_caps:
        eff = max(raw_zipf - caps_penalty, 0.0)
    else:
        eff = raw_zipf
    return eff, is_caps


def _extract_context(text: str, word: str, context_chars: int = 60) -> str:
    """Find *word* in *text* and return a short surrounding snippet."""
    idx = text.find(word)
    if idx == -1:
        # Try case-insensitive
        idx = text.lower().find(word.lower())
    if idx == -1:
        return ""
    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(word) + context_chars)
    snippet = text[start:end].replace('\n', ' ').replace('\t', ' ')
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


# ──────────────────────────────────────────────────────────────
# Main detection function
# ──────────────────────────────────────────────────────────────

def detect_rare_words(
    parsed_models: list,
    config: RareWordConfig,
) -> List[RareWord]:
    """
    Scan CDE items and return rare words sorted by CDE count (descending).

    Parameters
    ----------
    parsed_models : list
        Parsed Pydantic CDEItem instances.
    config : RareWordConfig
        Detection parameters.

    Returns
    -------
    list[RareWord]
        Words passing the rarity + CDE-frequency thresholds.
    """
    from wordfreq import zipf_frequency
    from logic.verbatim_discoverer import _extract_at_path

    # ── Pass 1: collect word → {tinyId}, word → field_set, word → example texts ──

    # word_form → canonical_form mapping (preserve the most common casing)
    word_tinyids: Dict[str, Set[str]] = defaultdict(set)
    word_fields: Dict[str, Set[str]] = defaultdict(set)    # "def" / "desig"
    word_form_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    word_example_texts: Dict[str, List[str]] = defaultdict(list)  # up to 3

    MAX_EXAMPLES = 3

    for model in parsed_models:
        tid = getattr(model, 'tinyId', None)
        if not tid:
            continue
        model_dict = model.model_dump(mode="python")

        for fp in config.field_names:
            texts = _extract_at_path(model_dict, fp.split('.'))
            # Determine field type for profile
            field_type = "def" if "definition" in fp else "desig"

            for text in texts:
                if not text or not isinstance(text, str):
                    continue
                words = _WORD_RE.findall(text)
                seen_in_text = set()  # avoid counting duplicates within same text
                for w in words:
                    if len(w) < config.min_word_len:
                        continue
                    # Use lowercase as the canonical key
                    key = w.lower()
                    if key in seen_in_text:
                        continue
                    seen_in_text.add(key)

                    word_tinyids[key].add(tid)
                    word_fields[key].add(field_type)
                    word_form_counts[key][w] += 1

                    # Collect example context snippets
                    if len(word_example_texts[key]) < MAX_EXAMPLES:
                        ctx = _extract_context(text, w)
                        if ctx:
                            word_example_texts[key].append(ctx)

    logger.info(f"Pass 1 complete: {len(word_tinyids)} unique word forms across "
                f"{len(parsed_models)} CDEs")

    # ── Pass 2: filter by CDE count, then by effective Zipf ──

    exclude_lower = set()
    if config.exclude_patterns:
        # Normalise exclusion set: split multi-word patterns into words
        for pat in config.exclude_patterns:
            for w in _WORD_RE.findall(pat):
                exclude_lower.add(w.lower())

    results: List[RareWord] = []

    for key, tids in word_tinyids.items():
        cde_count = len(tids)
        if cde_count < config.min_tinyids:
            continue

        # Skip words already covered by instrument/phrase patterns
        if key in exclude_lower:
            continue

        # Pick the dominant surface form (most frequent casing)
        form_counts = word_form_counts[key]
        dominant_form = max(form_counts, key=form_counts.get)

        # Zipf lookup (always lowercase)
        raw_zipf = zipf_frequency(key, 'en')
        eff_zipf, is_caps = compute_effective_zipf(dominant_form, raw_zipf, config.caps_penalty)

        if eff_zipf >= config.zipf_threshold:
            continue

        # Field profile
        fields = word_fields[key]
        if fields == {"def", "desig"}:
            profile = "def+desig"
        elif "def" in fields:
            profile = "def"
        else:
            profile = "desig"

        results.append(RareWord(
            word=dominant_form,
            cde_count=cde_count,
            raw_zipf=raw_zipf,
            effective_zipf=eff_zipf,
            is_allcaps=is_caps,
            field_profile=profile,
            tinyids=tids,
            example_contexts=word_example_texts[key][:MAX_EXAMPLES],
        ))

    # Sort by CDE count descending
    results.sort(key=lambda r: (-r.cde_count, r.word))

    logger.info(f"Pass 2 complete: {len(results)} rare words "
                f"(zipf_threshold={config.zipf_threshold}, "
                f"caps_penalty={config.caps_penalty}, "
                f"min_tinyids={config.min_tinyids})")

    return results
