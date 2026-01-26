#
# File: actions/strip_phrases/cli.py
#
"""
Strip Phrases - Remove curated phrases from CDE text fields.

Supports two input modes:
1. Discovered patterns (--patterns): TSV from strip_discover with pattern, tinyIds columns
2. Legacy phrase map (--phrases): JSON/CSV/TSV with path, phrase, replace, tinyIds columns

Workflow:
1. Run strip_discover to find patterns in CDE data
2. Curator reviews/edits discovered patterns
3. Run strip_phrases with --patterns to apply substitutions

Example:
  cde_analyzer strip_phrases -i input.json -m CDE -o output.json --patterns discovered.tsv
"""
from argparse import ArgumentParser
from utils.constants import MODEL_REGISTRY
from .run import run_action

help_text = "Remove curated phrases from specific paths in CDE records"
description_text = __doc__


def register_subparser(subparser: ArgumentParser):
    # Required: input and output
    subparser.add_argument(
        "--input", "-i", required=True, help="Path to input JSON file (CDE records)."
    )
    subparser.add_argument(
        "--model",
        "-m",
        choices=MODEL_REGISTRY.keys(),
        required=True,
        help="Top-level Pydantic model name for parsing the input JSON.",
    )
    subparser.add_argument(
        "--output", "-o", required=True, help="Path to output JSON file (cleaned records)."
    )

    # Pattern source: either --patterns OR --phrases (mutually exclusive)
    phrase_source = subparser.add_mutually_exclusive_group(required=True)
    phrase_source.add_argument(
        "--patterns",
        "-p",
        help="Path to discovered patterns TSV (from strip_discover). "
             "Format: pattern<TAB>tinyIds<TAB>type<TAB>source_pattern. "
             "Column matching is case-insensitive.",
    )
    phrase_source.add_argument(
        "--phrases",
        help="Path to legacy phrase map file (JSON, CSV, or TSV) with columns: "
             "path, phrase, replace, tinyIds.",
    )

    # Processing options
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to strip phrases from "
             "(default: definitions.*.definition designations.*.designation)",
    )
    subparser.add_argument(
        "--sort-order",
        choices=["length", "file", "alpha"],
        default="length",
        help="Pattern processing order: 'length' (longest-first, default), "
             "'file' (preserve TSV file order for curator control), "
             "'alpha' (alphabetical for reproducibility).",
    )

    # Parallelization
    subparser.add_argument(
        "--workers", "-w",
        type=int,
        default=1,
        help="Number of parallel workers for phrase stripping. "
             "Use 0 for auto-detect with headroom (n-1 CPUs for ≤10 cores, n-2 for >10). "
             "Use 1 for sequential (default). "
             "Positive values override to use exactly N workers.",
    )

    # Diagnostics
    subparser.add_argument(
        "--trace-matching",
        type=str,
        metavar="FILE",
        help="Write detailed matching trace to FILE. "
             "Logs each pattern match with tinyId, pattern length, and pattern text. "
             "Useful for debugging ordering issues or unexpected orphan phrases.",
    )

    # Diff output options
    subparser.add_argument(
        "--diff",
        "-d",
        action="store_true",
        help="Show diff between original and cleaned JSON",
    )
    subparser.add_argument(
        "--diff-output", type=str, help="Path to file for writing diff information."
    )
    subparser.add_argument(
        "--color", "-c", action="store_true", help="Colorize diff output."
    )
    subparser.add_argument(
        "--summary", action="store_true", help="Show a summary of changed lines."
    )
    subparser.add_argument(
        "--context",
        "-C",
        type=int,
        default=3,
        help="Number of context lines before and after changes.",
    )

    subparser.set_defaults(func=run_action)
