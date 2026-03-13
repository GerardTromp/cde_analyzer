#
# File: actions/instrument_util/cli.py
#
"""
Instrument hierarchy analysis and strip pattern generation.

Provides tools for analyzing instrument pattern hierarchies and generating
field-aware strip patterns for the branching strip pipeline:
- Group hierarchy assignment (shared prefix grouping)
- Semantic grouping with SpaCy POS tagging
- Field-aware instrument split analysis (Full/Sub decomposition)
- Strip pattern file generation (inst_full + inst_sub)

Usage Examples:

  # Assign group hierarchy
  cde-analyzer instrument_util --group-hierarchy coalesced.tsv -o grouped.tsv

  # Analyze for field-aware splits
  cde-analyzer instrument_util --analyze-instrument-splits curated.tsv \\
      --input cdes.json -o instrument_splits.tsv

  # Generate strip pattern files
  cde-analyzer instrument_util --generate-strip-patterns instrument_splits.tsv \\
      --input cdes.json -o inst_patterns
"""
from argparse import ArgumentParser

help_text = "Instrument hierarchy analysis and strip pattern generation"

description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Common args
    subparser.add_argument(
        "--output", "-o",
        help="Output path (file or directory, mode-dependent).",
    )
    subparser.add_argument(
        "--input", "-i",
        type=str,
        help="Path to CDE JSON file (required for --analyze-instrument-splits).",
    )
    subparser.add_argument(
        "--model", "-m",
        type=str,
        default="CDE",
        help="Model type for parsing JSON. See MODEL_REGISTRY.",
    )
    subparser.add_argument(
        "--fields",
        type=str,
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to scan.",
    )
    subparser.add_argument(
        "--workers", "-w",
        type=int,
        default=0,
        help="Number of parallel workers (0 = sequential).",
    )

    # Group hierarchy mode
    subparser.add_argument(
        "--group-hierarchy",
        type=str,
        metavar="FILE",
        help="Group hierarchy mode: assign group/sub_group labels to patterns. "
             "Groups patterns by shared prefix, strips trailing delimiters to get "
             "clean group names (e.g., 'PROMIS -' → 'PROMIS'). "
             "Input TSV must have 'pattern' and 'tinyIds' columns. "
             "Writes enriched output with group, sub_group, suffix columns to --output.",
    )
    subparser.add_argument(
        "--min-tinyids",
        type=int,
        default=0,
        help="Filter: drop patterns with fewer than N tinyIds before grouping. "
             "Removes noise patterns that appear on very few CDEs. "
             "This is the base minimum; if --min-tinyids-scale is set, the effective "
             "threshold is: base + floor(scale * sqrt(corpus_size)). "
             "Use with --group-hierarchy. 0 = disabled.",
    )
    subparser.add_argument(
        "--min-tinyids-scale",
        type=float,
        default=0.0,
        help="Scale factor for adaptive tinyId threshold: "
             "effective_min = min_tinyids + floor(scale * sqrt(N)), where N is the "
             "total unique tinyIds (corpus size). Incidental groupings increase as "
             "sqrt(N), so this adjusts the noise floor proportionally. "
             "Use with --group-hierarchy. 0.0 = disabled (use fixed --min-tinyids only).",
    )

    # Generate strip pattern files from hierarchy
    subparser.add_argument(
        "--generate-strip-patterns",
        type=str,
        metavar="FILE",
        help="Generate strip-ready pattern files from a group-hierarchy TSV. "
             "Produces two files: {output}_full.tsv (full removal) and "
             "{output}_sub.tsv (group prefix removed, suffix retained). "
             "Both files are ready for use with strip_phrases --patterns. "
             "If the input contains 'proposed_full' and 'proposed_sub' columns "
             "(output of --analyze-instrument-splits after curation), uses "
             "field-aware splits mode producing genuinely different pattern "
             "text in full vs sub files.",
    )

    # Analyze instrument patterns for field-aware full/sub splits
    subparser.add_argument(
        "--analyze-instrument-splits",
        type=str,
        metavar="FILE",
        help="Analyze curated instrument patterns for field-aware full/sub "
             "splits. Input: curated patterns TSV (pattern + tinyIds columns). "
             "Requires --input (CDE JSON) for frequency analysis. "
             "Produces a curation TSV with proposed_full, proposed_sub, "
             "separator, and frequency columns for curator review.",
    )

    # Semantic grouping mode
    subparser.add_argument(
        "--group-semantic",
        type=str,
        metavar="FILE",
        help="Semantic grouping mode: group patterns by shared prefix spans, "
             "trimming boundaries using SpaCy POS tagging to avoid overshooting "
             "into content-bearing tokens. Input TSV must have 'pattern' and "
             "'tinyIds' columns. Writes grouped output to --output with "
             "group_prefix, group_size, group_tinyid_count columns.",
    )
    subparser.add_argument(
        "--min-group-size",
        type=int,
        default=2,
        help="Minimum patterns per semantic group.",
    )
    subparser.add_argument(
        "--min-prefix-words",
        type=int,
        default=2,
        help="Minimum words in shared prefix to form a group.",
    )
    subparser.add_argument(
        "--no-temporal-implied",
        action="store_true",
        help="Disable generation of implied-ONE temporal variants. By default, "
             "for each temporal group with an explicit quantifier (e.g., 'In the past 7 days'), "
             "an implied-ONE form is also emitted (e.g., 'In the past day'). "
             "These catch singular temporal frames that exist on different CDE records. "
             "Use this flag to suppress that behavior.",
    )

    subparser.set_defaults(run=_get_run_action())
