#
# File: actions/diagnose_strip/cli.py
#
"""
Diagnose Strip - Analyze cleaned JSON for remaining anchor patterns.

Provides iterative diagnostics for improving the strip_discover/strip_phrases
workflow by identifying patterns that weren't captured.

Workflow:
1. Load cleaned JSON from strip_phrases output
2. Search for anchor patterns ("as part of", "based on", etc.)
3. Extract and count patterns following each anchor
4. Generate TSV report with frequencies
5. Optionally generate YAML suggestions for supplementary_patterns.yaml

Example:
    cde_analyzer diagnose_strip -i cleaned.json -m CDE -o remaining.tsv --suggest-patterns
"""
from argparse import ArgumentParser
from utils.constants import MODEL_REGISTRY
from .run import run_action

help_text = "Diagnose remaining anchor patterns after stripping"
description_text = __doc__


def register_subparser(subparser: ArgumentParser):
    """Register CLI arguments for diagnose_strip action."""

    # Required arguments
    subparser.add_argument(
        "--input", "-i",
        required=True,
        help="Input JSON file (cleaned output from strip_phrases)",
    )

    subparser.add_argument(
        "--model", "-m",
        choices=MODEL_REGISTRY.keys(),
        required=True,
        help="Pydantic model name (CDE, Form)",
    )

    subparser.add_argument(
        "--output", "-o",
        required=True,
        help="Output TSV file with remaining patterns and frequencies",
    )

    # Optional arguments
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to search for remaining patterns. "
             "Default: definitions.*.definition designations.*.designation",
    )

    subparser.add_argument(
        "--original",
        help="Optional: Original JSON file (before stripping) for comparison metrics",
    )

    subparser.add_argument(
        "--anchors",
        nargs="+",
        default=["as part of", "as a part of", "based on", "field of"],
        help="Anchor phrases to search for. Default: 'as part of' 'as a part of' 'based on' 'field of'",
    )

    subparser.add_argument(
        "--context-chars",
        type=int,
        default=100,
        help="Characters of context to capture after anchor (default: 100)",
    )

    subparser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Minimum occurrence count to include in output (default: 1)",
    )

    subparser.add_argument(
        "--suggest-patterns",
        action="store_true",
        help="Output suggested patterns for config/supplementary_patterns.yaml",
    )

    subparser.set_defaults(func=run_action)
