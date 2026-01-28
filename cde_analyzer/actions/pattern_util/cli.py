#
# File: actions/pattern_util/cli.py
#
"""
Pattern Util - TSV pattern manipulation utilities.

Provides utilities for working with pattern TSV files:
- Merge: Combine duplicate pattern rows, merging tinyIds
- Coalesce: Remove subsumed patterns (tinyId-aware subsumption)
- Import: Add curated patterns to supplementary_patterns.yaml

These utilities work on TSV files only - no CDE JSON input required.

Usage Examples:

  # Merge duplicate patterns
  cde-analyzer pattern_util --merge-patterns discovered.tsv -o merged.tsv

  # Coalesce patterns (remove subsumed)
  cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv

  # Coalesce with prefix extraction
  cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \\
      --min-prefix-tinyids 3 --coalesce-report report.tsv

  # Import curated patterns to config
  cde-analyzer pattern_util --add-to-supplementary curated.tsv
"""
from argparse import ArgumentParser

help_text = "TSV pattern utilities (merge, coalesce, import)"

description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Output (required for merge/coalesce)
    subparser.add_argument(
        "--output", "-o",
        help="Path to output TSV file. Required for merge and coalesce modes."
    )

    # Merge mode
    subparser.add_argument(
        "--merge-patterns",
        type=str,
        metavar="FILE",
        help="Merge mode: read curated TSV, combine rows with identical patterns, "
             "merge their tinyId sets, and write deduplicated output to --output. "
             "When specified, ignores other options and just performs the merge.",
    )
    subparser.add_argument(
        "--merge-pattern-column",
        type=str,
        default="pattern",
        help="Column name for patterns in merge mode (default: 'pattern').",
    )
    subparser.add_argument(
        "--merge-tinyids-column",
        type=str,
        default="tinyIds",
        help="Column name for tinyIds in merge mode (default: 'tinyIds').",
    )

    # Coalesce mode (tinyId-aware subsumption)
    subparser.add_argument(
        "--coalesce-variants",
        type=str,
        metavar="FILE",
        help="Coalesce mode: remove shorter patterns subsumed by longer ones. "
             "A pattern is subsumed if it's a substring of longer pattern(s) AND "
             "its tinyIds are covered by the union of those longer patterns' tinyIds. "
             "Example: 'in the past 7 days' is subsumed by 'in the past 7 days:' and "
             "'in the past 7 days - ' if all tinyIds are covered. "
             "Writes coalesced patterns to --output.",
    )
    subparser.add_argument(
        "--coalesce-report",
        type=str,
        metavar="FILE",
        help="Write subsumption report showing which patterns were removed and why.",
    )
    subparser.add_argument(
        "--min-prefix-tinyids",
        type=int,
        default=0,
        help="Enable prefix extraction during coalesce: groups patterns by common prefix "
             "and replaces them with the shortest prefix meeting this tinyId threshold. "
             "Example: 'as part of Neuro-QOL Lower...' and 'as part of Neuro-QOL Upper...' "
             "become 'as part of Neuro-QOL' if it covers enough tinyIds. "
             "Use with --coalesce-variants. Default 0 = disabled.",
    )
    subparser.add_argument(
        "--min-parent-tinyids",
        type=int,
        default=0,
        help="Filter patterns by parent phrase tinyId count during coalesce. "
             "Drops patterns whose parent_tinyid_count < this threshold. "
             "Requires input TSV with parent_phrase and parent_tinyid_count columns "
             "(produced by strip_discover --parent-column). Default 0 = disabled.",
    )

    # Supplementary pattern import mode
    subparser.add_argument(
        "--add-to-supplementary",
        type=str,
        metavar="CURATED_TSV",
        help="Import mode: add patterns from curated TSV to supplementary_patterns.yaml. "
             "TSV must have 'pattern' and 'name' columns. Optional 'acronym' column. "
             "Patterns are added to 'added_patterns' section. File is deleted after import. "
             "Use after reviewing --analyze-false-negatives output from strip_analyze.",
    )
    subparser.add_argument(
        "--supplementary-section",
        type=str,
        default="added_patterns",
        help="YAML section name for imported patterns (default: 'added_patterns').",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
