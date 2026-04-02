#
# File: actions/abbreviation/cli.py
#
"""
Abbreviation discovery, expansion, classification, and dictionary management.

Provides a systematic pipeline for resolving abbreviations in CDE text:
  discover → expand → classify → export strip patterns

Usage Examples:

  # Discover all abbreviations in a CDE JSON corpus
  cde-analyzer abbreviation --discover -i cdes.json -o discovered.tsv

  # Expand abbreviations using internal context (definitions)
  cde-analyzer abbreviation --expand discovered.tsv -i cdes.json -o expanded.tsv

  # Classify expanded abbreviations by heuristic rules
  cde-analyzer abbreviation --classify expanded.tsv -o classified.tsv

  # Export strip patterns from classified entries
  cde-analyzer abbreviation --export-strip classified.tsv -o local_verbatim.yaml

  # Export tinyId-scoped bare-tag patterns
  cde-analyzer abbreviation --export-scoped classified.tsv -o scoped_tags.tsv

  # Print dictionary statistics
  cde-analyzer abbreviation --stats dictionary.tsv

  # Merge two dictionaries (update overwrites base)
  cde-analyzer abbreviation --merge base.tsv update.tsv -o merged.tsv
"""
from argparse import ArgumentParser

help_text = "Abbreviation discovery, expansion, and dictionary management"

description_text = __doc__


def _get_run_action():
    from actions.abbreviation.run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    subparser.add_argument(
        "--input", "-i",
        help="Path to CDE JSON file (required for --discover, --expand).",
    )
    subparser.add_argument(
        "--output", "-o",
        help="Output file path.",
    )
    subparser.add_argument(
        "--model", "-m",
        default="CDE",
        help="Data model (default: CDE).",
    )

    # Modes (mutually exclusive)
    group = subparser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--discover",
        action="store_true",
        help="Discover abbreviations in CDE corpus. Finds parenthetical (ABBREV), "
             "bracketed [TAG], bare CAPS, and InterCaps patterns.",
    )
    group.add_argument(
        "--expand",
        type=str,
        metavar="DICT_TSV",
        help="Expand abbreviations in dictionary TSV using CDE definitions. "
             "Requires --input for CDE JSON.",
    )
    group.add_argument(
        "--classify",
        type=str,
        metavar="DICT_TSV",
        help="Classify abbreviations in dictionary TSV using heuristic rules.",
    )
    group.add_argument(
        "--export-strip",
        type=str,
        metavar="DICT_TSV",
        help="Export strip patterns (YAML) from classified dictionary entries.",
    )
    group.add_argument(
        "--export-scoped",
        type=str,
        metavar="DICT_TSV",
        help="Export tinyId-scoped patterns (TSV) for bare abbreviation stripping.",
    )
    group.add_argument(
        "--stats",
        type=str,
        metavar="DICT_TSV",
        help="Print summary statistics of a dictionary TSV.",
    )
    group.add_argument(
        "--merge",
        nargs=2,
        metavar=("BASE_TSV", "UPDATE_TSV"),
        help="Merge two dictionaries. UPDATE overwrites BASE on conflict.",
    )
    group.add_argument(
        "--pipeline",
        action="store_true",
        help="Run full pipeline: discover → expand → classify → seed from "
             "reference dictionary → export strip + scoped patterns. "
             "Requires --input and --output (directory).",
    )

    # Options
    subparser.add_argument(
        "--categories",
        type=str,
        default="instrument,study",
        help="Comma-separated categories to export (default: instrument,study).",
    )
    subparser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.8,
        help="Confidence threshold for needs_review export (default: 0.8).",
    )
    subparser.add_argument(
        "--min-occurrences",
        type=int,
        default=1,
        help="Minimum tinyId count to include in discovery (default: 1).",
    )
    subparser.add_argument(
        "--no-intercaps",
        action="store_true",
        help="Skip InterCaps/medial capital discovery.",
    )

    subparser.set_defaults(func=_get_run_action())
