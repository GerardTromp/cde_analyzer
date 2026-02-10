#
# File: actions/diagnose_strip/run.py
#
"""
Diagnose Strip - Run module for stripping diagnostics.

Analyzes cleaned JSON to identify remaining anchor patterns
and generate actionable reports for iterative improvement.
"""
import json
import re
from argparse import Namespace
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from utils.logger import logging
from utils.file_utils import exit_if_missing, graceful_interrupt
from pydantic import ValidationError
from utils.constants import MODEL_REGISTRY

logger = logging.getLogger(__name__)


def extract_field_values(item, field_paths: List[str]) -> List[Tuple[str, str, str]]:
    """
    Extract text values from specified field paths.

    Args:
        item: Pydantic model instance
        field_paths: List of dotted paths like "definitions.*.definition"

    Returns:
        List of (tinyId, field_path, text) tuples
    """
    results = []
    tinyId = getattr(item, 'tinyId', 'unknown')

    for field_path in field_paths:
        parts = field_path.split('.')

        def extract_recursive(obj, remaining_parts: List[str], current_path: str):
            if not remaining_parts:
                if isinstance(obj, str):
                    results.append((tinyId, current_path, obj))
                return

            part = remaining_parts[0]
            rest = remaining_parts[1:]

            if part == '*':
                # Wildcard: iterate over list
                if isinstance(obj, list):
                    for i, item in enumerate(obj):
                        extract_recursive(item, rest, f"{current_path}[{i}]")
            else:
                # Named attribute
                if hasattr(obj, part):
                    val = getattr(obj, part)
                    if val is not None:
                        new_path = f"{current_path}.{part}" if current_path else part
                        extract_recursive(val, rest, new_path)

        extract_recursive(item, parts, '')

    return results


def find_anchor_patterns(
    text: str,
    anchors: List[str],
    context_chars: int = 100
) -> List[Tuple[str, str, str]]:
    """
    Find anchor patterns and extract context after them.

    Args:
        text: Text to search
        anchors: List of anchor phrases to find
        context_chars: How many characters to capture after anchor

    Returns:
        List of (anchor, context, full_match) tuples
    """
    results = []

    for anchor in anchors:
        # Case-insensitive search
        pattern = re.compile(re.escape(anchor), re.IGNORECASE)
        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()

            # Extract context after anchor
            context_end = min(end + context_chars, len(text))
            context = text[end:context_end].strip()

            # Extract full match including context up to sentence end or newline
            full_end = end
            for i, c in enumerate(text[end:end + context_chars]):
                if c in '.!?\n':
                    full_end = end + i + 1
                    break
                full_end = end + i + 1

            full_match = text[start:full_end].strip()

            results.append((anchor, context, full_match))

    return results


def normalize_pattern(context: str) -> str:
    """
    Normalize a context string for grouping similar patterns.

    Strips trailing punctuation and normalizes whitespace.
    """
    # Remove trailing punctuation and whitespace
    normalized = context.strip()
    normalized = re.sub(r'[.,;:!?]+$', '', normalized)
    # Normalize internal whitespace
    normalized = ' '.join(normalized.split())
    return normalized


def categorize_pattern(pattern: str) -> str:
    """
    Categorize a pattern for grouping in reports.

    Returns category like 'questionnaire', 'test', 'model', 'scale', etc.
    """
    lower = pattern.lower()

    if any(kw in lower for kw in ['questionnaire', 'survey', 'form']):
        return 'questionnaire'
    elif any(kw in lower for kw in [' test', 'test ']):
        return 'test'
    elif 'model' in lower:
        return 'model'
    elif any(kw in lower for kw in ['scale', 'score', 'index']):
        return 'scale'
    elif any(kw in lower for kw in ['version', 'v1', 'v2']):
        return 'version'
    elif re.search(r'\([A-Z]{2,}\)', pattern):
        return 'acronym'
    else:
        return 'other'


def generate_yaml_suggestion(pattern: str, count: int) -> Optional[str]:
    """
    Generate a YAML entry suggestion for a pattern.

    Returns a formatted YAML snippet or None if pattern doesn't look like an instrument.
    """
    # Skip very short patterns
    if len(pattern) < 5:
        return None

    # Skip patterns that look like generic text
    generic_indicators = [
        'the study', 'this study', 'our study', 'the data', 'this data',
        'the following', 'the patient', 'speech therapy', 'medical history'
    ]
    lower = pattern.lower()
    if any(ind in lower for ind in generic_indicators):
        return None

    # Capitalize for display name
    display_name = pattern.title()

    # Extract acronym if present
    acronym_match = re.search(r'\(([A-Z][A-Z0-9-]+)\)', pattern)
    acronym = acronym_match.group(1) if acronym_match else None

    # Format YAML
    lines = [f'  - pattern: "{pattern}"']
    lines.append(f'    name: "{display_name}"')
    if acronym:
        lines.append(f'    acronym: "{acronym}"')
    lines.append(f'    # Found {count}x in corpus')

    return '\n'.join(lines)


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for diagnose_strip action."""

    model_class = MODEL_REGISTRY[args.model]

    # Load cleaned data
    input_path = exit_if_missing(args.input, "Input file")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            print(f"Error Type: {error['type']}")
            print(f"Message: {error['msg']}")
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} records from {args.input}")

    # Load original data if provided (for comparison)
    original_parsed = None
    if args.original:
        original_path = exit_if_missing(args.original, "Original file")
        with open(original_path, encoding="utf-8") as f:
            original_data = json.load(f)
        try:
            original_parsed = [model_class.model_validate(obj) for obj in original_data]
        except ValidationError:
            logger.warning("Could not parse original file, skipping comparison")
            original_parsed = None

    # Configuration
    anchors = args.anchors
    context_chars = args.context_chars
    field_paths = args.fields
    min_count = args.min_count

    # Collect all remaining anchor patterns
    pattern_counter: Counter = Counter()
    pattern_tinyids: Dict[str, Set[str]] = defaultdict(set)
    pattern_examples: Dict[str, str] = {}

    logger.info(f"Scanning {len(parsed)} records for anchor patterns...")

    for item in parsed:
        fields = extract_field_values(item, field_paths)
        tinyId = getattr(item, 'tinyId', 'unknown')

        for _, field_path, text in fields:
            matches = find_anchor_patterns(text, anchors, context_chars)
            for anchor, context, full_match in matches:
                normalized = normalize_pattern(context)
                if normalized:
                    pattern_counter[normalized] += 1
                    pattern_tinyids[normalized].add(tinyId)
                    if normalized not in pattern_examples:
                        pattern_examples[normalized] = full_match

    # Filter by minimum count
    filtered_patterns = [
        (pattern, count)
        for pattern, count in pattern_counter.most_common()
        if count >= min_count
    ]

    # Calculate comparison metrics if original provided
    original_count = 0
    if original_parsed:
        for item in original_parsed:
            fields = extract_field_values(item, field_paths)
            for _, _, text in fields:
                for anchor in anchors:
                    original_count += len(re.findall(re.escape(anchor), text, re.IGNORECASE))

    remaining_count = sum(count for _, count in filtered_patterns)

    # Write output TSV
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("pattern\tcount\tnum_tinyids\tcategory\texample\n")

        for pattern, count in filtered_patterns:
            tinyids = pattern_tinyids[pattern]
            category = categorize_pattern(pattern)
            example = pattern_examples.get(pattern, '')
            # Escape tabs/newlines in example
            example_escaped = example.replace('\t', ' ').replace('\n', ' ')

            f.write(f"{pattern}\t{count}\t{len(tinyids)}\t{category}\t{example_escaped}\n")

    logger.info(f"Wrote {len(filtered_patterns)} remaining patterns to {args.output}")

    # Print summary
    print(f"\n{'=' * 60}")
    print("STRIPPING DIAGNOSTICS SUMMARY")
    print('=' * 60)

    if original_parsed:
        stripped_count = original_count - remaining_count
        pct_stripped = (stripped_count / original_count * 100) if original_count > 0 else 0
        print(f"\nComparison with original:")
        print(f"  Original anchor occurrences: {original_count}")
        print(f"  Remaining anchor occurrences: {remaining_count}")
        print(f"  Stripped: {stripped_count} ({pct_stripped:.1f}%)")

    print(f"\nRemaining patterns: {len(filtered_patterns)} unique")
    print(f"Total occurrences: {remaining_count}")

    # Group by category
    category_counts = Counter()
    for pattern, count in filtered_patterns:
        category = categorize_pattern(pattern)
        category_counts[category] += count

    print(f"\nBy category:")
    for category, count in category_counts.most_common():
        print(f"  {category}: {count}")

    # Top patterns
    print(f"\nTop 10 remaining patterns:")
    for i, (pattern, count) in enumerate(filtered_patterns[:10], 1):
        # Truncate long patterns for display
        display = pattern[:50] + '...' if len(pattern) > 50 else pattern
        print(f"  {i:2}. ({count:4}x) {display}")

    print(f"\nOutput: {args.output}")

    # Generate YAML suggestions if requested
    if args.suggest_patterns:
        suggest_file = Path(args.output).with_suffix('.yaml')

        # Group by category for YAML output
        by_category = defaultdict(list)
        for pattern, count in filtered_patterns[:50]:  # Top 50
            suggestion = generate_yaml_suggestion(pattern, count)
            if suggestion:
                category = categorize_pattern(pattern)
                by_category[category].append(suggestion)

        with open(suggest_file, 'w', encoding='utf-8') as f:
            f.write("# Suggested additions to config/supplementary_patterns.yaml\n")
            f.write("# Review each entry before adding - not all patterns are instruments!\n\n")

            for category, suggestions in sorted(by_category.items()):
                f.write(f"# === {category.upper()} ===\n")
                f.write(f"{category}_suggested:\n")
                for suggestion in suggestions:
                    f.write(suggestion + '\n\n')

        print(f"\nPattern suggestions: {suggest_file}")

    return 0
