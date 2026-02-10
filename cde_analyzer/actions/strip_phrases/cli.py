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

help_text = "Remove curated phrases from specific paths in CDE records"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


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
        help="Discovered patterns TSV (from strip_discover or curated merge). "
             "Format: 'file.tsv' (uses 'pattern' column), "
             "'file.tsv,column_name' (custom pattern column), or "
             "'file.tsv,pattern_col,tinyids_col' (both custom). "
             "Column matching is case-insensitive. "
             "Excel-quoted fields are automatically unquoted.",
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
             "(default: definitions.*.definition designations.*.designation). "
             "Also supports: valueDomain.permissibleValues.*.valueMeaningName, "
             "valueDomain.permissibleValues.*.valueMeaningDefinition",
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

    # Remnant detection
    subparser.add_argument(
        "--detect-remnants",
        action="store_true",
        help="After stripping, scan output for post-strip artifacts "
             "(orphan articles, floating punctuation, excess whitespace, etc.).",
    )
    subparser.add_argument(
        "--remnant-report",
        type=str,
        metavar="FILE",
        help="Write detailed remnant report TSV to FILE. Implies --detect-remnants.",
    )
    subparser.add_argument(
        "--clean-remnants",
        action="store_true",
        help="After stripping, apply iterative cleanup to fix post-strip artifacts "
             "(remove orphan articles, floating punctuation, excess whitespace, etc.). "
             "Modifies the output JSON in-place before writing.",
    )

    # Case-insensitive matching
    subparser.add_argument(
        "--ignore-case",
        action="store_true",
        default=False,
        help="Case-insensitive pattern matching. Patterns like 'In the past' "
             "will also match 'in the past' and 'IN THE PAST'.",
    )

    # Word boundary matching
    subparser.add_argument(
        "--word-boundary",
        action="store_true",
        default=False,
        help="Use word boundary anchors (\\b) for pattern matching. "
             "Prevents partial-word matches: 'in the past' will NOT match "
             "inside 'within the past'. Composable with --ignore-case.",
    )

    # Anchor expansion (improves stripping by matching with context)
    subparser.add_argument(
        "--expand-anchors",
        dest="expand_anchors",
        action="store_true",
        default=True,
        help="Expand patterns with anchor prefixes (e.g., 'as part of the X'). "
             "Enables cleaner stripping by matching longer context. Default: enabled.",
    )
    subparser.add_argument(
        "--no-expand-anchors",
        dest="expand_anchors",
        action="store_false",
        help="Disable anchor prefix expansion. Use bare patterns only.",
    )

    # Verbatim patterns from config (reusable pattern library)
    subparser.add_argument(
        "--verbatim-patterns",
        dest="verbatim_patterns",
        action="store_true",
        default=True,
        help="Merge patterns from config/verbatim_strip_patterns.yaml and local override. "
             "These are pre-curated patterns that escape discovery logic. Default: enabled.",
    )
    subparser.add_argument(
        "--no-verbatim-patterns",
        dest="verbatim_patterns",
        action="store_false",
        help="Disable loading verbatim patterns from config files.",
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
    subparser.add_argument(
        "--match-log",
        type=str,
        metavar="FILE",
        help="Write detailed match log TSV to FILE. "
             "Columns: tinyId, matched_pattern, source_pattern, verbatim_text. "
             "Full audit trail of what was stripped and where.",
    )
    subparser.add_argument(
        "--match-summary",
        type=str,
        metavar="FILE",
        help="Write pattern match summary TSV to FILE. "
             "Columns: source_pattern, match_count, unique_records. "
             "Aggregated counts of how many times each pattern was stripped.",
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

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
