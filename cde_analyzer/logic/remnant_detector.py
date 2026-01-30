#
# File: logic/remnant_detector.py
#
"""
Post-strip remnant detector.

Scans CDE text fields for artifacts left behind after phrase stripping:
orphan articles, dangling punctuation, excess whitespace, empty parens, etc.

Usage:
    from logic.remnant_detector import detect_remnants, summarize_remnants

    remnants = detect_remnants(records, field_paths)
    summary = summarize_remnants(remnants)
"""
import csv
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


@dataclass
class Remnant:
    """A detected post-strip artifact."""
    tinyId: str
    field_path: str
    remnant_type: str
    text_snippet: str
    position: int


# Remnant patterns: (name, compiled regex, description)
# Each regex is designed to match artifacts commonly left after phrase removal.
_REMNANT_PATTERNS = [
    (
        "orphan_article",
        re.compile(r'\b(the|a|an)\s*[,.\-;:)]\s*$', re.IGNORECASE),
        "Trailing article before punctuation",
    ),
    (
        "trailing_article",
        re.compile(r'\b(the|a|an)\s*$', re.IGNORECASE),
        "Trailing article at end of text",
    ),
    (
        "leading_article",
        re.compile(r'^\s*(the|a|an)\s*[,.\-;:]', re.IGNORECASE),
        "Leading article followed by punctuation",
    ),
    (
        "dangling_s",
        re.compile(r"(?<=\s)'?s\b"),
        "Orphan possessive 's after whitespace",
    ),
    (
        "floating_punct",
        re.compile(r'(?<=\s)[,;:\-]{1,3}(?=\s)'),
        "Floating punctuation surrounded by spaces",
    ),
    (
        "excess_whitespace",
        re.compile(r'  +'),
        "Double or more spaces",
    ),
    (
        "orphan_preposition",
        re.compile(r'\b(of|for|in|on|at|by|to)\s*[,.\-;:)]\s*$', re.IGNORECASE),
        "Trailing preposition before punctuation",
    ),
    (
        "empty_parens",
        re.compile(r'\(\s*\)'),
        "Empty parentheses",
    ),
    (
        "empty_brackets",
        re.compile(r'\[\s*\]'),
        "Empty brackets",
    ),
    (
        "leading_punct",
        re.compile(r'^\s*[,;:\-]'),
        "Leading punctuation",
    ),
    (
        "trailing_punct_space",
        re.compile(r'\s+[,;:.]\s*$'),
        "Space before trailing punctuation",
    ),
    (
        "double_punct",
        re.compile(r'[,;:]{2,}'),
        "Repeated punctuation",
    ),
]


def _extract_at_path(obj: Any, parts: List[str]) -> List[tuple]:
    """
    Extract (value, realized_path) pairs at a dotted path with wildcard support.

    Returns list of (string_value, path_string) tuples.
    """
    if not parts:
        if isinstance(obj, str):
            return [(obj, "")]
        return []

    key = parts[0]
    rest = parts[1:]
    results = []

    if key == '*':
        if isinstance(obj, list):
            for i, item in enumerate(obj):
                for val, subpath in _extract_at_path(item, rest):
                    results.append((val, f"{i}.{subpath}" if subpath else str(i)))
    elif isinstance(obj, dict):
        if key in obj:
            for val, subpath in _extract_at_path(obj[key], rest):
                results.append((val, f"{key}.{subpath}" if subpath else key))
    elif isinstance(obj, list):
        try:
            idx = int(key)
            if 0 <= idx < len(obj):
                for val, subpath in _extract_at_path(obj[idx], rest):
                    results.append((val, f"{key}.{subpath}" if subpath else key))
        except ValueError:
            pass

    return results


def _scan_text(text: str) -> List[tuple]:
    """
    Scan a single text string for remnant patterns.

    Returns list of (remnant_type, snippet, position) tuples.
    """
    hits = []
    for name, pattern, _desc in _REMNANT_PATTERNS:
        for match in pattern.finditer(text):
            # Context snippet: up to 30 chars around the match
            start = max(0, match.start() - 15)
            end = min(len(text), match.end() + 15)
            snippet = text[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            hits.append((name, snippet, match.start()))
    return hits


def detect_remnants(
    records: List[Any],
    field_paths: Optional[List[str]] = None,
) -> List[Remnant]:
    """
    Scan records for post-strip artifacts.

    Args:
        records: List of Pydantic model instances (must have tinyId attribute).
        field_paths: Dot-separated field paths with wildcard support.
                     Default: definitions.*.definition, designations.*.designation

    Returns:
        List of Remnant instances found.
    """
    if field_paths is None:
        field_paths = [
            "definitions.*.definition",
            "designations.*.designation",
        ]

    remnants = []

    for record in records:
        tiny_id = getattr(record, 'tinyId', '') or ''
        record_dict = record.model_dump(mode="json") if hasattr(record, 'model_dump') else record

        for field_path in field_paths:
            parts = field_path.split('.')
            for text_value, realized_subpath in _extract_at_path(record_dict, parts):
                if not text_value or not text_value.strip():
                    continue

                hits = _scan_text(text_value)
                for remnant_type, snippet, position in hits:
                    remnants.append(Remnant(
                        tinyId=tiny_id,
                        field_path=field_path,
                        remnant_type=remnant_type,
                        text_snippet=snippet,
                        position=position,
                    ))

    logger.info(f"Detected {len(remnants)} remnants across {len(records)} records")
    return remnants


def detect_remnants_from_json(
    data: List[dict],
    field_paths: Optional[List[str]] = None,
) -> List[Remnant]:
    """
    Scan raw JSON dicts (no Pydantic) for post-strip artifacts.

    Args:
        data: List of record dicts (must have 'tinyId' key).
        field_paths: Dot-separated field paths with wildcard support.

    Returns:
        List of Remnant instances found.
    """
    if field_paths is None:
        field_paths = [
            "definitions.*.definition",
            "designations.*.designation",
        ]

    remnants = []

    for record in data:
        tiny_id = record.get('tinyId', '') or ''

        for field_path in field_paths:
            parts = field_path.split('.')
            for text_value, realized_subpath in _extract_at_path(record, parts):
                if not text_value or not text_value.strip():
                    continue

                hits = _scan_text(text_value)
                for remnant_type, snippet, position in hits:
                    remnants.append(Remnant(
                        tinyId=tiny_id,
                        field_path=field_path,
                        remnant_type=remnant_type,
                        text_snippet=snippet,
                        position=position,
                    ))

    logger.info(f"Detected {len(remnants)} remnants across {len(data)} records")
    return remnants


def summarize_remnants(remnants: List[Remnant]) -> Dict[str, int]:
    """
    Count remnants by type.

    Returns:
        Dict mapping remnant_type -> count.
    """
    counts: Dict[str, int] = {}
    for r in remnants:
        counts[r.remnant_type] = counts.get(r.remnant_type, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def affected_records(remnants: List[Remnant]) -> int:
    """Count unique tinyIds with at least one remnant."""
    return len(set(r.tinyId for r in remnants if r.tinyId))


def write_remnant_report(
    remnants: List[Remnant],
    output_path: str,
) -> None:
    """
    Write remnant report as TSV.

    Columns: tinyId, field_path, remnant_type, text_snippet, position
    """
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['tinyId', 'field_path', 'remnant_type', 'text_snippet', 'position'])
        for r in remnants:
            writer.writerow([r.tinyId, r.field_path, r.remnant_type, r.text_snippet, r.position])

    # Also write summary at the end
    summary = summarize_remnants(remnants)
    logger.info(f"Wrote {len(remnants)} remnants to {output_path}")
    logger.info(f"Summary: {summary}")
    logger.info(f"Affected records: {affected_records(remnants)}")
