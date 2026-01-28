#
# File: actions/recall_analyze/run.py
#
# Orchestration for recall analysis and false-negative detection
#

import csv
import json
import logging
import re
import sys
from argparse import Namespace
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from utils.file_utils import graceful_interrupt
from utils.constants import MODEL_REGISTRY
from logic.subset import extract_field_texts_from_dict, load_patterns_from_file
from utils.pattern_tsv_utils import find_column_name

logger = logging.getLogger(__name__)


def load_pipeline_tinyids(
    pipeline_file: str,
    tinyid_column: str,
) -> Dict[str, Set[str]]:
    """
    Load tinyIds from pipeline output TSV, grouped by pattern/row.

    Returns dict mapping row identifier to set of tinyIds.
    Also builds a flat set of all pipeline tinyIds for quick lookup.
    """
    all_tinyids: Set[str] = set()

    with open(pipeline_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')

        try:
            actual_column = find_column_name(reader.fieldnames, tinyid_column)
        except ValueError:
            logger.error(f"Column '{tinyid_column}' not found in {pipeline_file}")
            logger.info(f"Available columns: {reader.fieldnames}")
            return {}

        for row in reader:
            tinyid_str = row.get(actual_column, '')
            if tinyid_str:
                # Handle both pipe and space separators
                if '|' in tinyid_str:
                    tinyids = [t.strip() for t in tinyid_str.split('|') if t.strip()]
                else:
                    tinyids = [t.strip() for t in tinyid_str.split() if t.strip()]
                all_tinyids.update(tinyids)

    logger.info(f"Loaded {len(all_tinyids)} unique tinyIds from pipeline output")
    return all_tinyids


def auto_label_pattern(pattern_str: str) -> str:
    """
    Derive a family label from a pattern string.

    Extracts abbreviation from parenthetical suffix like "(HAM-A)" → "HAM-A",
    or returns a short version of the pattern text.

    Examples:
        "Hamilton Anxiety Rating Scale (HAM-A)" → "HAM-A"
        "Patient Health Questionnaire" → "Patient Health Questionnaire"
        "PROMIS - Emotional Distress depression" → "PROMIS-EDD"
    """
    # Look for trailing parenthetical abbreviation: (HAM-A), (CES-D), (PROMIS), (GDS)
    abbrev_match = re.search(r'\(([A-Z][A-Za-z0-9-]+)\)\s*$', pattern_str)
    if abbrev_match:
        return abbrev_match.group(1)

    # No parenthetical — return the pattern text as-is (will be used as label)
    return pattern_str.strip()


def is_plain_text_pattern(pattern_str: str) -> bool:
    """
    Detect whether a pattern is plain text (not intended as regex).

    Returns True if the pattern appears to be literal text rather than
    a crafted regex. Heuristic: if it contains regex metacharacters but
    lacks typical regex constructs like character classes [ ], quantifiers,
    or escaped characters, it's probably plain text.

    Examples:
        "Hamilton Anxiety Rating Scale (HAM-A)" → True (literal parens)
        "Patient[ -]Health[ -]Questionnaire"    → False (has char classes)
        "Quality of Life"                        → True (no special chars)
        "PROMIS[ -][-][ -]Emotional"            → False (has char classes)
    """
    # If pattern contains character class brackets with content, it's regex
    if re.search(r'\[.+?\]', pattern_str):
        return False
    # If pattern contains common regex escapes, it's regex
    if re.search(r'\\[dDwWsSbB()\[\]]', pattern_str):
        return False
    # If pattern contains unescaped regex metacharacters that look intentional
    # (anchors, quantifiers, alternation) it's regex
    if re.search(r'(?<!\\)[*+?|^$]', pattern_str):
        return False
    # Otherwise it's plain text (even if it has parens — those are literal)
    return True


def make_flexible_pattern(pattern_str: str) -> str:
    """
    Convert a plain-text pattern to a flexible regex.

    Escapes regex special characters, then replaces spaces and hyphens
    with [ -] for flexible matching (space/hyphen interchangeable).

    Examples:
        "Hamilton Anxiety Rating Scale (HAM-A)"
            → "Hamilton[ -]Anxiety[ -]Rating[ -]Scale[ -]\\(HAM\\-A\\)"
        "Quality of Life"
            → "Quality[ -]of[ -]Life"
    """
    # First escape all regex special characters
    escaped = re.escape(pattern_str)
    # re.escape turns spaces into '\ ' — replace escaped spaces with [ -]
    # Also replace escaped hyphens \- with [ -] for flexible matching
    result = escaped.replace(r'\ ', '[ -]').replace(r'\-', '[ -]')
    return result


def find_source_matches(
    data: List[Dict],
    patterns: List[Tuple[str, str]],  # (pattern, label)
    field_names: List[str],
    case_sensitive: bool = False,
) -> Dict[str, Dict[str, Set[str]]]:
    """
    Find all source matches for patterns, grouped by label (instrument family).

    Patterns can be either regex or plain text. If a pattern fails regex
    compilation, it is automatically escaped and converted to a flexible
    pattern (spaces/hyphens interchangeable). Unlabeled patterns get
    auto-derived labels from parenthetical abbreviations like (HAM-A).

    Returns:
        Dict[label, Dict[pattern, Set[tinyId]]]
    """
    flags = 0 if case_sensitive else re.IGNORECASE

    # Compile patterns — auto-escape plain text patterns for flexible matching
    compiled = []
    for pattern_str, label in patterns:
        # Auto-derive label if not provided
        effective_label = label or auto_label_pattern(pattern_str)

        if is_plain_text_pattern(pattern_str):
            # Plain text: escape and convert to flexible regex
            flexible = make_flexible_pattern(pattern_str)
            try:
                regex = re.compile(flexible, flags)
                compiled.append((regex, pattern_str, effective_label))
                logger.debug(f"Plain text pattern '{pattern_str}' → '{flexible}'")
            except re.error as e:
                logger.warning(f"Cannot compile pattern '{pattern_str}' after escaping: {e}, skipping")
        else:
            # Already a regex pattern
            try:
                regex = re.compile(pattern_str, flags)
                compiled.append((regex, pattern_str, effective_label))
            except re.error as e:
                logger.warning(f"Invalid regex '{pattern_str}': {e}, skipping")

    # Group results by label -> pattern -> tinyIds
    results: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    for record in data:
        tinyid = record.get("tinyId")
        if not tinyid:
            continue

        texts = extract_field_texts_from_dict(record, field_names)
        if not texts:
            continue

        # Check each pattern
        for regex, pattern_str, label in compiled:
            for text in texts:
                if regex.search(text):
                    results[label][pattern_str].add(tinyid)
                    break  # Found match for this pattern, move to next

    return dict(results)


def compute_recall_metrics(
    source_matches: Dict[str, Dict[str, Set[str]]],
    pipeline_tinyids: Set[str],
) -> List[Dict]:
    """
    Compute recall metrics per family and pattern.

    Returns list of metric rows for TSV output.
    """
    rows = []

    for label in sorted(source_matches.keys()):
        patterns = source_matches[label]

        # Aggregate all tinyIds for this family
        family_source_tinyids: Set[str] = set()
        for tinyids in patterns.values():
            family_source_tinyids.update(tinyids)

        # Compute family-level metrics
        family_pipeline_tinyids = family_source_tinyids & pipeline_tinyids
        family_missing = family_source_tinyids - pipeline_tinyids

        family_recall = (
            len(family_pipeline_tinyids) / len(family_source_tinyids)
            if family_source_tinyids else 0.0
        )

        # Add family summary row
        rows.append({
            'family': label,
            'pattern': f"[FAMILY: {label}]",
            'source_count': len(family_source_tinyids),
            'pipeline_count': len(family_pipeline_tinyids),
            'missing_count': len(family_missing),
            'recall': f"{family_recall:.3f}",
            'missing_tinyids': '|'.join(sorted(family_missing)[:20]),  # Limit for readability
        })

        # Add per-pattern rows
        for pattern_str in sorted(patterns.keys()):
            pattern_tinyids = patterns[pattern_str]
            pattern_pipeline = pattern_tinyids & pipeline_tinyids
            pattern_missing = pattern_tinyids - pipeline_tinyids

            pattern_recall = (
                len(pattern_pipeline) / len(pattern_tinyids)
                if pattern_tinyids else 0.0
            )

            rows.append({
                'family': label,
                'pattern': pattern_str,
                'source_count': len(pattern_tinyids),
                'pipeline_count': len(pattern_pipeline),
                'missing_count': len(pattern_missing),
                'recall': f"{pattern_recall:.3f}",
                'missing_tinyids': '|'.join(sorted(pattern_missing)),
            })

    return rows


def write_recall_report(rows: List[Dict], output_path: str) -> None:
    """Write recall metrics to TSV file."""
    fieldnames = ['family', 'pattern', 'source_count', 'pipeline_count',
                  'missing_count', 'recall', 'missing_tinyids']

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        if rows:
            writer.writerows(rows)
        else:
            logger.warning("No recall metrics — writing header-only TSV")

    logger.info(f"Wrote recall report with {len(rows)} rows to {output_path}")


def write_false_negatives_by_family(
    source_matches: Dict[str, Dict[str, Set[str]]],
    pipeline_tinyids: Set[str],
    output_path: str,
) -> None:
    """Write false negative tinyIds grouped by family."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for label in sorted(source_matches.keys()):
            # Get all source tinyIds for this family
            family_source: Set[str] = set()
            for tinyids in source_matches[label].values():
                family_source.update(tinyids)

            # Find missing
            missing = family_source - pipeline_tinyids

            if missing:
                f.write(f"# {label} ({len(missing)} missing)\n")
                for tinyid in sorted(missing):
                    f.write(f"{tinyid}\n")
                f.write("\n")

    logger.info(f"Wrote false negatives by family to {output_path}")


# =============================================================================
# Pattern Suggestion Functions
# =============================================================================

def extract_designation_prefix(designation: str) -> Tuple[str, Optional[str]]:
    """
    Extract designation prefix up to first delimiter and detect embedded abbreviation.

    Args:
        designation: Full designation string

    Returns:
        Tuple of (prefix_text, detected_abbreviation or None)

    Examples:
        "Patient Health Questionnaire (PHQ-9) - depressed mood"
            → ("Patient Health Questionnaire (PHQ-9)", "PHQ")
        "Geriatric Depression Scale (GDS) Long Form - score"
            → ("Geriatric Depression Scale (GDS) Long Form", "GDS")
    """
    import re

    # Pattern to detect embedded abbreviation parentheticals
    abbrev_pattern = re.compile(r'\(([A-Z]+)(?:-\d+)?\)')

    # Delimiters that end the instrument name portion
    # Order matters: longer delimiters first
    delimiters = [' - ', ' -- ', ' – ', ': ']

    # Find first delimiter
    prefix = designation
    for delim in delimiters:
        idx = designation.find(delim)
        if idx > 0:
            prefix = designation[:idx]
            break

    # Detect abbreviation in prefix
    match = abbrev_pattern.search(prefix)
    abbrev = match.group(1) if match else None

    return prefix.strip(), abbrev


def generate_suggested_pattern(prefix: str, abbreviation: Optional[str]) -> str:
    """
    Generate a flexible regex pattern from a designation prefix.

    Handles:
    - Optional spacing between words: "Patient[ -]Health[ -]Questionnaire"
    - Abbreviation variants: "(PHQ)" → "(PHQ(?:-\\d+)?)"

    Args:
        prefix: Designation prefix text
        abbreviation: Detected abbreviation (e.g., "PHQ") or None

    Returns:
        Regex pattern string
    """
    import re

    # Tokenize prefix, preserving parenthetical groups
    tokens = re.findall(r'\([^)]+\)|\S+', prefix)

    pattern_parts = []
    for i, token in enumerate(tokens):
        if i > 0:
            # Flexible word separator: space, hyphen, or nothing
            pattern_parts.append(r'[ -]')

        # Handle parenthetical abbreviation
        if token.startswith('(') and token.endswith(')'):
            inner = token[1:-1]
            # Check if it's an abbreviation (all caps, possibly with number)
            if re.match(r'^[A-Z]+(?:-\d+)?$', inner):
                # Make the number part optional for matching variants
                base_match = re.match(r'^([A-Z]+)', inner)
                if base_match:
                    base = base_match.group(1)
                    pattern_parts.append(rf'\({re.escape(base)}(?:-\d+)?\)')
                else:
                    pattern_parts.append(r'\(' + re.escape(inner) + r'\)')
            else:
                pattern_parts.append(r'\(' + re.escape(inner) + r'\)')
        else:
            pattern_parts.append(re.escape(token))

    return ''.join(pattern_parts)


def suggest_patterns_for_family(
    family_name: str,
    false_negative_tinyids: Set[str],
    data: List[Dict],
    field_names: List[str],
    min_matches: int = 2,
) -> List[Dict]:
    """
    Analyze false negatives for a family and suggest enhanced patterns.

    Args:
        family_name: Instrument family label
        false_negative_tinyids: Set of tinyIds that are false negatives
        data: Full CDE JSON data
        field_names: Fields to search for designations
        min_matches: Minimum matches required for a pattern to be suggested

    Returns:
        List of suggestion dicts with keys:
        - pattern: Suggested regex pattern
        - suggested_label: Family name for the pattern
        - matched_count: Number of false negatives matched
        - source_tinyIds: Space-separated list of matched tinyIds
    """
    import re
    from collections import defaultdict

    # Collect all designations from false negatives
    designations_by_tinyid = {}
    for record in data:
        tinyid = record.get('tinyId')
        if tinyid not in false_negative_tinyids:
            continue

        texts = extract_field_texts_from_dict(record, field_names)
        if texts:
            designations_by_tinyid[tinyid] = texts

    # Extract prefixes and detect abbreviations
    prefix_data = []  # List of (prefix, abbrev, tinyid)
    for tinyid, texts in designations_by_tinyid.items():
        for text in texts:
            prefix, abbrev = extract_designation_prefix(text)
            if prefix:
                prefix_data.append((prefix, abbrev, tinyid))

    # Build candidate patterns and count matches
    pattern_matches = defaultdict(set)  # pattern -> set of matched tinyIds

    for prefix, abbrev, tinyid in prefix_data:
        suggested = generate_suggested_pattern(prefix, abbrev)
        pattern_matches[suggested].add(tinyid)

    # Filter by min_matches and compile results
    suggestions = []
    for pattern, tinyids in pattern_matches.items():
        if len(tinyids) >= min_matches:
            suggestions.append({
                'pattern': pattern,
                'suggested_label': family_name,
                'matched_count': len(tinyids),
                'source_tinyIds': ' '.join(sorted(tinyids)),
            })

    # Sort by match count descending
    suggestions.sort(key=lambda x: -x['matched_count'])

    return suggestions


def write_suggested_patterns_tsv(
    suggestions: List[Dict],
    output_path: str,
) -> None:
    """Write suggested patterns to TSV file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("pattern\tsuggested_label\tmatched_count\tsource_tinyIds\n")
        for s in suggestions:
            f.write(f"{s['pattern']}\t{s['suggested_label']}\t{s['matched_count']}\t{s['source_tinyIds']}\n")

    logger.info(f"Wrote {len(suggestions)} suggested patterns to {output_path}")


def load_previous_report(report_path: str) -> Dict[str, Dict]:
    """
    Load a previous recall report for comparison.

    Returns dict mapping family -> {pipeline_count, missing_count, recall}
    """
    results = {}

    with open(report_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')

        for row in reader:
            # Only load family summary rows
            if row['pattern'].startswith('[FAMILY:'):
                family = row['family']
                results[family] = {
                    'pipeline_count': int(row['pipeline_count']),
                    'missing_count': int(row['missing_count']),
                    'recall': float(row['recall']),
                }

    logger.info(f"Loaded {len(results)} family metrics from previous report")
    return results


def compute_marginal_gains(
    current_rows: List[Dict],
    previous_metrics: Dict[str, Dict],
) -> Tuple[List[Dict], int]:
    """
    Compare current results against previous iteration to compute gains.

    Returns:
        - List of gain rows for output
        - Total new CDEs captured
    """
    gains = []
    total_new = 0

    for row in current_rows:
        if not row['pattern'].startswith('[FAMILY:'):
            continue

        family = row['family']
        current_captured = int(row['pipeline_count'])

        if family in previous_metrics:
            prev_captured = previous_metrics[family]['pipeline_count']
            delta = current_captured - prev_captured
        else:
            # New family not in previous report
            prev_captured = 0
            delta = current_captured

        total_new += max(0, delta)

        gains.append({
            'family': family,
            'previous_captured': prev_captured,
            'current_captured': current_captured,
            'delta': delta,
            'current_recall': row['recall'],
        })

    return gains, total_new


def load_version_history(markdown_path: str) -> List[Dict]:
    """
    Load version history from an existing markdown report.

    Parses the Version History table if present.
    Returns list of version dicts with: version, date, families, captured, recall, notes
    """
    import os
    if not os.path.exists(markdown_path):
        return []

    history = []
    in_version_table = False
    header_seen = False

    with open(markdown_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Look for version history section
            if line == '## Version History':
                in_version_table = True
                continue

            if in_version_table:
                # Skip empty lines
                if not line:
                    continue

                # Skip markdown table header separator
                if line.startswith('|---') or line.startswith('| ---'):
                    header_seen = True
                    continue

                # Skip header row
                if line.startswith('| Version') or line.startswith('|Version'):
                    continue

                # Stop at next section
                if line.startswith('## ') or line.startswith('# '):
                    break

                # Parse table row
                if line.startswith('|') and header_seen:
                    parts = [p.strip() for p in line.split('|')]
                    # Remove empty parts from leading/trailing |
                    parts = [p for p in parts if p]

                    if len(parts) >= 5:
                        history.append({
                            'version': parts[0],
                            'date': parts[1],
                            'families': parts[2],
                            'captured': parts[3],
                            'recall': parts[4],
                            'notes': parts[5] if len(parts) > 5 else '',
                        })

    return history


def generate_markdown_report(
    title: str,
    version: str,
    rows: List[Dict],
    source_matches: Dict[str, Dict[str, Set[str]]],
    pipeline_tinyids: Set[str],
    patterns: List[Tuple[str, str]],
    total_source: int,
    gains: List[Dict] = None,
    previous_report: str = None,
    total_new: int = 0,
    stopping_met: bool = False,
    stopping_threshold: int = 2,
    min_recall: float = 0.0,
    version_history: List[Dict] = None,
    input_file: str = None,
    pattern_file: str = None,
    pipeline_output: str = None,
) -> str:
    """
    Generate a markdown report with summary and per-family details.

    Returns the complete markdown content as a string.
    """
    from datetime import datetime

    lines = []
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Title and metadata
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Generated**: {date_str}")
    if version:
        lines.append(f"**Version**: {version}")
    lines.append("")

    # Input files section
    lines.append("## Input Files")
    lines.append("")
    if input_file:
        lines.append(f"- **Source JSON**: `{input_file}`")
    if pattern_file:
        lines.append(f"- **Pattern File**: `{pattern_file}`")
    if pipeline_output:
        lines.append(f"- **Pipeline Output**: `{pipeline_output}`")
    lines.append("")

    # Summary section
    family_rows = [r for r in rows if r['pattern'].startswith('[FAMILY:')]
    perfect_recall = [r for r in family_rows if float(r['recall']) >= 1.0]
    low_recall = [r for r in family_rows if float(r['recall']) < min_recall] if min_recall > 0 else []

    total_captured = sum(int(r['pipeline_count']) for r in family_rows)
    total_missing = sum(int(r['missing_count']) for r in family_rows)
    overall_recall = total_captured / total_source if total_source > 0 else 0.0

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Patterns | {len(patterns)} |")
    lines.append(f"| Instrument Families | {len(family_rows)} |")
    lines.append(f"| Source Matches (Ground Truth) | {total_source} |")
    lines.append(f"| Pipeline Captured | {total_captured} |")
    lines.append(f"| Missing (False Negatives) | {total_missing} |")
    lines.append(f"| **Overall Recall** | **{overall_recall:.1%}** |")
    lines.append(f"| Families at 100% Recall | {len(perfect_recall)} |")
    if min_recall > 0:
        lines.append(f"| Families Below {min_recall:.0%} Threshold | {len(low_recall)} |")
    lines.append("")

    # Stopping criterion status
    if gains is not None:
        lines.append("### Iteration Status")
        lines.append("")
        if stopping_met:
            lines.append(f"> **STOPPING CRITERION MET**: Marginal gain ({total_new}) ≤ threshold ({stopping_threshold})")
            lines.append("> Diminishing returns reached - consider stopping iteration.")
        else:
            lines.append(f"> Marginal gain ({total_new}) > threshold ({stopping_threshold}) - continue iterating")
        lines.append("")

        if previous_report:
            lines.append(f"Compared against: `{previous_report}`")
            lines.append("")

    # Recall by family table
    lines.append("### Recall by Family")
    lines.append("")
    lines.append("| Family | Source | Captured | Missing | Recall | Status |")
    lines.append("|--------|-------:|--------:|--------:|-------:|--------|")

    for r in sorted(family_rows, key=lambda x: float(x['recall'])):
        recall_val = float(r['recall'])
        if recall_val >= 1.0:
            status = "✓ Complete"
        elif recall_val >= 0.9:
            status = "○ Good"
        elif recall_val >= 0.7:
            status = "△ Needs Work"
        else:
            status = "✗ Low"

        lines.append(
            f"| {r['family']} | {r['source_count']} | {r['pipeline_count']} | "
            f"{r['missing_count']} | {recall_val:.1%} | {status} |"
        )
    lines.append("")

    # Iteration gains table (if comparing)
    if gains:
        lines.append("### Iteration Gains")
        lines.append("")
        lines.append("| Family | Previous | Current | Delta | Recall |")
        lines.append("|--------|--------:|--------:|------:|-------:|")
        for g in sorted(gains, key=lambda x: -x['delta']):
            delta_str = f"+{g['delta']}" if g['delta'] > 0 else str(g['delta'])
            lines.append(
                f"| {g['family']} | {g['previous_captured']} | {g['current_captured']} | "
                f"{delta_str} | {g['current_recall']} |"
            )
        lines.append("")
        lines.append(f"**Total New CDEs Captured**: {total_new}")
        lines.append("")

    # Details by family
    lines.append("---")
    lines.append("")
    lines.append("## Details by Family")
    lines.append("")

    for label in sorted(source_matches.keys()):
        pattern_dict = source_matches[label]

        # Get family metrics from rows
        family_row = next((r for r in family_rows if r['family'] == label), None)
        if not family_row:
            continue

        recall_val = float(family_row['recall'])
        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"**Recall**: {recall_val:.1%} ({family_row['pipeline_count']}/{family_row['source_count']})")
        lines.append("")

        if int(family_row['missing_count']) > 0:
            lines.append(f"**Missing**: {family_row['missing_count']} tinyIds")
            lines.append("")

        # Pattern details
        lines.append("#### Patterns")
        lines.append("")
        lines.append("| Pattern | Source | Captured | Missing | Recall |")
        lines.append("|---------|-------:|--------:|--------:|-------:|")

        for pattern_str in sorted(pattern_dict.keys()):
            # Find this pattern's row
            pattern_row = next(
                (r for r in rows if r['family'] == label and r['pattern'] == pattern_str),
                None
            )
            if pattern_row:
                p_recall = float(pattern_row['recall'])
                # Truncate long patterns for readability
                display_pattern = pattern_str if len(pattern_str) <= 50 else pattern_str[:47] + "..."
                # Escape pipe characters in pattern
                display_pattern = display_pattern.replace('|', '\\|')
                lines.append(
                    f"| `{display_pattern}` | {pattern_row['source_count']} | "
                    f"{pattern_row['pipeline_count']} | {pattern_row['missing_count']} | {p_recall:.1%} |"
                )
        lines.append("")

        # Missing tinyIds (if any and not too many)
        if int(family_row['missing_count']) > 0:
            family_source: Set[str] = set()
            for tinyids in pattern_dict.values():
                family_source.update(tinyids)
            missing = family_source - pipeline_tinyids

            if len(missing) <= 20:
                lines.append("#### Missing tinyIds")
                lines.append("")
                lines.append("```")
                for tid in sorted(missing):
                    lines.append(tid)
                lines.append("```")
                lines.append("")
            else:
                lines.append(f"#### Missing tinyIds ({len(missing)} total)")
                lines.append("")
                lines.append("See `--false-negatives-file` output for complete list.")
                lines.append("")

    # Version history section
    lines.append("---")
    lines.append("")
    lines.append("## Version History")
    lines.append("")
    lines.append("| Version | Date | Families | Captured | Recall | Notes |")
    lines.append("|---------|------|----------|----------|--------|-------|")

    # Add previous versions
    if version_history:
        for vh in version_history:
            lines.append(
                f"| {vh['version']} | {vh['date']} | {vh['families']} | "
                f"{vh['captured']} | {vh['recall']} | {vh['notes']} |"
            )

    # Add current version
    current_notes = ""
    if stopping_met:
        current_notes = "Stopping criterion met"
    elif gains:
        current_notes = f"+{total_new} CDEs"

    lines.append(
        f"| {version or 'current'} | {date_str.split()[0]} | {len(family_rows)} | "
        f"{total_captured} | {overall_recall:.1%} | {current_notes} |"
    )
    lines.append("")

    return '\n'.join(lines)


def write_markdown_report(
    report_path: str,
    content: str,
) -> None:
    """Write markdown report to file."""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Wrote markdown report to {report_path}")


@graceful_interrupt
def run_action(args: Namespace):
    """
    Analyze recall by comparing source pattern matches against pipeline output.

    Outputs:
    - Recall report with metrics per family and pattern
    - Optional false negatives file grouped by family
    """
    # Load source JSON
    logger.info(f"Loading source CDE JSON from {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("error: Input JSON must be a list of records.", file=sys.stderr)
        sys.exit(2)

    logger.info(f"Loaded {len(data)} records from source")

    # Load patterns with labels
    patterns = load_patterns_from_file(args.pattern_file)
    if not patterns:
        print("error: No valid patterns found in pattern file.", file=sys.stderr)
        sys.exit(2)

    # Count labeled vs unlabeled
    labeled = sum(1 for _, label in patterns if label)
    logger.info(f"Loaded {len(patterns)} patterns ({labeled} with labels)")

    # Find source matches
    logger.info(f"Searching source data for pattern matches in fields: {args.fields}")
    source_matches = find_source_matches(
        data=data,
        patterns=patterns,
        field_names=args.fields,
        case_sensitive=args.case_sensitive,
    )

    # Summarize source matches
    total_source = 0
    for label, pattern_dict in source_matches.items():
        family_total = len(set().union(*pattern_dict.values()))
        total_source += family_total
        logger.info(f"  {label}: {family_total} unique tinyIds")

    # Load pipeline output if provided
    if args.pipeline_output:
        pipeline_tinyids = load_pipeline_tinyids(
            args.pipeline_output,
            args.pipeline_tinyid_column,
        )
        if not pipeline_tinyids:
            print("warning: No tinyIds loaded from pipeline output.", file=sys.stderr)
            pipeline_tinyids = set()
    else:
        logger.info("No pipeline output provided - reporting source matches only")
        pipeline_tinyids = set()

    # Compute recall metrics
    rows = compute_recall_metrics(source_matches, pipeline_tinyids)

    # Write recall report
    write_recall_report(rows, args.output)

    # Write false negatives file if requested
    if args.false_negatives_file and pipeline_tinyids:
        write_false_negatives_by_family(
            source_matches,
            pipeline_tinyids,
            args.false_negatives_file,
        )

    # Print summary
    family_rows = [r for r in rows if r['pattern'].startswith('[FAMILY:')]

    print(f"\nRecall Analysis Complete:")
    print(f"  Patterns: {len(patterns)}")
    print(f"  Families: {len(family_rows)}")
    print(f"  Source matches: {total_source} unique tinyIds")

    if pipeline_tinyids:
        # Show families below min_recall threshold
        low_recall = [r for r in family_rows if float(r['recall']) < args.min_recall]
        perfect_recall = [r for r in family_rows if float(r['recall']) >= 1.0]

        print(f"  Pipeline tinyIds: {len(pipeline_tinyids)}")
        print(f"  Families with 100% recall: {len(perfect_recall)}")

        if low_recall:
            print(f"\n  Families below {args.min_recall:.0%} recall:")
            for r in low_recall:
                print(f"    {r['family']}: {r['recall']} ({r['missing_count']} missing)")

    # Compare with previous iteration if provided
    previous_report = getattr(args, 'previous_report', None)
    stopping_threshold = getattr(args, 'stopping_threshold', 2)

    # Initialize for markdown report
    gains = None
    total_new = 0
    stopping_met = False

    if previous_report:
        logger.info(f"Comparing with previous report: {previous_report}")
        previous_metrics = load_previous_report(previous_report)
        gains, total_new = compute_marginal_gains(rows, previous_metrics)

        print(f"\n  Iteration Comparison:")
        print(f"    Previous report: {previous_report}")
        print(f"    New CDEs captured: {total_new}")

        # Show per-family gains
        if gains:
            print(f"\n    Per-family gains:")
            for g in sorted(gains, key=lambda x: -x['delta']):
                if g['delta'] != 0:
                    sign = "+" if g['delta'] > 0 else ""
                    print(f"      {g['family']}: {g['previous_captured']} → {g['current_captured']} ({sign}{g['delta']})")

        # Check stopping criterion
        stopping_met = total_new <= stopping_threshold
        if stopping_met:
            print(f"\n  *** STOPPING CRITERION MET ***")
            print(f"    Marginal gain ({total_new}) <= threshold ({stopping_threshold})")
            print(f"    Diminishing returns reached - consider stopping iteration")
        else:
            print(f"\n    Marginal gain ({total_new}) > threshold ({stopping_threshold}) - continue iterating")

    # Generate markdown report if requested
    markdown_report_path = getattr(args, 'markdown_report', None)
    if markdown_report_path:
        report_version = getattr(args, 'report_version', None)
        report_title = getattr(args, 'report_title', 'Instrument Detection Recall Report')

        # Load version history from existing markdown report (if it exists)
        version_history = load_version_history(markdown_report_path)

        markdown_content = generate_markdown_report(
            title=report_title,
            version=report_version,
            rows=rows,
            source_matches=source_matches,
            pipeline_tinyids=pipeline_tinyids,
            patterns=patterns,
            total_source=total_source,
            gains=gains,
            previous_report=previous_report,
            total_new=total_new,
            stopping_met=stopping_met,
            stopping_threshold=stopping_threshold,
            min_recall=args.min_recall,
            version_history=version_history,
            input_file=args.input,
            pattern_file=args.pattern_file,
            pipeline_output=args.pipeline_output,
        )

        write_markdown_report(markdown_report_path, markdown_content)
        print(f"  Markdown report: {markdown_report_path}")

    # Write standalone phase detail report if requested
    markdown_detail_path = getattr(args, 'markdown_detail', None)
    if markdown_detail_path:
        # Generate a standalone report (same content, separate file)
        detail_version = getattr(args, 'report_version', None)
        detail_title = getattr(args, 'report_title', 'Instrument Detection Recall Report')
        if detail_version:
            detail_title = f"{detail_title} — {detail_version}"

        detail_content = generate_markdown_report(
            title=detail_title,
            version=detail_version,
            rows=rows,
            source_matches=source_matches,
            pipeline_tinyids=pipeline_tinyids,
            patterns=patterns,
            total_source=total_source,
            gains=gains,
            previous_report=previous_report,
            total_new=total_new,
            stopping_met=stopping_met,
            stopping_threshold=stopping_threshold,
            min_recall=args.min_recall,
            version_history=None,  # No version history in standalone detail
            input_file=args.input,
            pattern_file=args.pattern_file,
            pipeline_output=args.pipeline_output,
        )

        write_markdown_report(markdown_detail_path, detail_content)
        print(f"  Phase detail report: {markdown_detail_path}")

    # Generate pattern suggestions if requested
    suggest_output = getattr(args, 'suggest_patterns', None)
    if suggest_output and pipeline_tinyids:
        min_recall_threshold = args.min_recall if args.min_recall > 0 else 0.7
        suggest_min_matches = getattr(args, 'suggest_min_matches', 2)

        all_suggestions = []

        for label in sorted(source_matches.keys()):
            # Get family metrics
            family_row = next((r for r in family_rows if r['family'] == label), None)
            if not family_row:
                continue

            recall_val = float(family_row['recall'])
            if recall_val >= min_recall_threshold:
                continue  # Skip families with sufficient recall

            # Get false negative tinyIds for this family
            family_source: Set[str] = set()
            for tinyids in source_matches[label].values():
                family_source.update(tinyids)
            false_negatives = family_source - pipeline_tinyids

            if not false_negatives:
                continue

            logger.info(f"Analyzing {len(false_negatives)} false negatives for {label}...")

            suggestions = suggest_patterns_for_family(
                family_name=label,
                false_negative_tinyids=false_negatives,
                data=data,
                field_names=args.fields,
                min_matches=suggest_min_matches,
            )

            all_suggestions.extend(suggestions)
            if suggestions:
                logger.info(f"  Generated {len(suggestions)} pattern suggestions for {label}")

        if all_suggestions:
            write_suggested_patterns_tsv(all_suggestions, suggest_output)
            print(f"  Pattern suggestions: {suggest_output}")
            print(f"    {len(all_suggestions)} patterns suggested for families with recall < {min_recall_threshold:.0%}")
        else:
            logger.info("No pattern suggestions generated (all families above threshold or no qualifying patterns)")

    print(f"\n  Output: {args.output}")

    return 0
