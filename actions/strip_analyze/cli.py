#
# File: actions/strip_analyze/cli.py
#
"""
Strip Analyze - Pattern analysis utilities for the stripping workflow.

Provides analysis modes for the iterative pattern stripping workflow:
- Conflict Analysis: Detect pattern containment issues that affect stripping order
- False-Negative Analysis: Find remaining anchor patterns after stripping

These analyses help curators identify:
1. Patterns that may interfere with each other during stripping
2. Patterns that were missed and need to be added

Usage Examples:

  # Analyze pattern conflicts (ordering issues)
  cde-analyzer strip_analyze --analyze-conflicts report.tsv \\
      --pattern-list instruments.tsv --sort-order length

  # Analyze false negatives (remaining patterns after stripping)
  cde-analyzer strip_analyze --analyze-false-negatives \\
      -i cleaned.json -o false_negatives.tsv --fn-anchor "as part of"

Output:
  - Conflict report: TSV with containment relationships and recommendations
  - False-negative report: TSV with remaining patterns and counts
"""
from argparse import ArgumentParser

help_text = "Analyze patterns for conflicts and false negatives"

description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Input (required for false-negative mode)
    subparser.add_argument(
        "--input", "-i",
        help="Path to cleaned JSON file (output from strip_phrases). "
             "Required for --analyze-false-negatives."
    )

    # Output (required for both modes)
    subparser.add_argument(
        "--output", "-o",
        help="Path to output TSV file. Required for analysis modes."
    )

    # Pattern list (required for conflict analysis)
    subparser.add_argument(
        "--pattern-list", "-p",
        help="TSV file with patterns to analyze. Required for --analyze-conflicts. "
             "Format: 'filename' (uses 'pattern' column) or 'filename,column_name'.",
    )

    # Conflict analysis mode
    subparser.add_argument(
        "--analyze-conflicts",
        type=str,
        metavar="FILE",
        help="Analysis mode: detect pattern containment conflicts that affect stripping order. "
             "Finds cases where pattern A is contained in pattern B, meaning order matters. "
             "Outputs TSV report with: short_pattern, long_pattern, relationship (prefix/suffix/interior), "
             "position, remainder, and recommendations. Requires --pattern-list.",
    )
    subparser.add_argument(
        "--sort-order",
        choices=["length", "file", "alpha"],
        default="length",
        help="Pattern processing order for conflict analysis: 'length' (longest-first, default), "
             "'file' (preserve TSV file order), 'alpha' (alphabetical).",
    )

    # Variant expansion for conflict analysis
    subparser.add_argument(
        "--expand-variants",
        action="store_true",
        help="Generate spelling/punctuation/number variants for pattern analysis.",
    )
    subparser.add_argument(
        "--include-name-only",
        action="store_true",
        default=True,
        help="When expanding variants, also include bare instrument names "
             "without 'as part of' prefix.",
    )
    subparser.add_argument(
        "--no-include-name-only",
        action="store_false",
        dest="include_name_only",
        help="Disable including bare instrument names in variant expansion.",
    )

    # False-negative analysis mode
    subparser.add_argument(
        "--analyze-false-negatives",
        action="store_true",
        help="Analysis mode: analyze remaining 'as part of' patterns in -i/--input JSON. "
             "Extracts patterns not fully stripped, counts occurrences, suggests candidates "
             "for supplementary_patterns.yaml. Outputs report to --output (TSV format) "
             "and displays summary to terminal. Requires --input and --output.",
    )
    subparser.add_argument(
        "--fn-anchor",
        type=str,
        default="as part of",
        help="Anchor phrase to search for in false-negative analysis.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
