#
# File: actions/strip_discover/cli.py
#
"""
Strip Discover - Discover instrument patterns in CDE text fields.

Flexible regex discovery tool for finding verbatim pattern occurrences.
Outputs a TSV file for curator review before stripping.

Primary Workflow:
1. Load patterns from --pattern-list (TSV with pattern column)
2. Optionally expand variants (--expand-variants)
3. Compile flexible regex patterns
4. Discover verbatim occurrences in CDE fields
5. Optionally discover bare names (--discover-bare-names)
6. Write discovered patterns TSV to --output

Iterative Improvement Workflow:
1. Run primary workflow to discover and strip patterns
2. Use --analyze-false-negatives on cleaned output to find remaining patterns
3. Review output TSV and set 'include' column to 'yes' for patterns to add
4. Use --add-to-supplementary to import curated patterns to config
5. Re-run phrase_miner with --extract-supplementary to pick up new patterns
6. Repeat until false negatives are acceptable

Output format:
  pattern<TAB>tinyIds<TAB>type<TAB>source_pattern

Where:
  - pattern: Verbatim text discovered in CDE fields
  - tinyIds: Space-separated list of CDE tinyIds where found
  - type: 'prefix' (with anchor like "as part of") or 'bare' (instrument name only)
  - source_pattern: Original pattern from pattern list (empty for bare names)
"""
from argparse import ArgumentParser
from utils.constants import MODEL_REGISTRY

help_text = "Discover instrument patterns in CDE text fields"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Core arguments (required for most modes, validated per-mode in run.py)
    subparser.add_argument(
        "--input", "-i", help="Path to input JSON file (CDE records or cleaned JSON for analysis)."
    )
    subparser.add_argument(
        "--model",
        "-m",
        choices=MODEL_REGISTRY.keys(),
        help="Top-level Pydantic model name for parsing the input JSON. "
             "Required for discovery mode, not needed for --analyze-false-negatives.",
    )
    subparser.add_argument(
        "--output", "-o", help="Path to output TSV file. Required for discovery and analysis modes."
    )

    # Pattern source (required for discovery mode, not needed for analysis modes)
    subparser.add_argument(
        "--pattern-list",
        "-p",
        help="TSV file with patterns to discover. Required for discovery mode. "
             "Format: 'filename' (uses 'full_match' column), 'filename,column_name', "
             "or 'filename,pattern_col,tinyids_col' (for --use-expected-tinyids). "
             "Column matching is case-insensitive.",
    )
    subparser.add_argument(
        "--additional-patterns",
        type=str,
        action="append",
        dest="additional_pattern_lists",
        help="Additional TSV files to merge with --pattern-list. Can be specified multiple times. "
             "Format: 'filename' or 'filename,column_name'.",
    )

    # Discovery options
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to search for patterns "
             "(default: definitions.*.definition designations.*.designation)",
    )
    subparser.add_argument(
        "--expand-variants",
        action="store_true",
        help="Generate spelling/punctuation/number variants for better matching. "
             "Handles: spacing around parentheses, trailing punctuation (including ' - ', ': '), "
             "prefix variations, possessive forms (Parkinson/Parkinson's), "
             "and number words (7/seven, 30/thirty for temporal phrases).",
    )
    subparser.add_argument(
        "--include-name-only",
        action="store_true",
        default=True,
        help="When expanding variants, also include bare instrument names "
             "without 'as part of' prefix. (default: True)",
    )
    subparser.add_argument(
        "--no-include-name-only",
        action="store_false",
        dest="include_name_only",
        help="Disable including bare instrument names in variant expansion.",
    )
    subparser.add_argument(
        "--discover-bare-names",
        action="store_true",
        help="Second pass: after discovering prefixed patterns, also discover "
             "bare instrument names (without anchor prefix). This finds occurrences "
             "like 'SF-12' that appear without 'as part of' prefix.",
    )
    subparser.add_argument(
        "--use-expected-tinyids",
        action="store_true",
        help="Use tinyIds from pattern list to filter discovery scope. "
             "Each pattern is only searched in texts from its expected tinyIds. "
             "Requires pattern list with tinyIds column. Column name can be specified "
             "as third element of --pattern-list spec (e.g., 'file.tsv,full_match,tinyids'). "
             "Column matching is case-insensitive.",
    )

    # Parallelization
    subparser.add_argument(
        "--workers", "-w",
        type=int,
        default=1,
        help="Number of parallel workers for discovery. "
             "Use 0 for auto-detect with headroom (n-1 CPUs for ≤10 cores, n-2 for >10). "
             "Use 1 for sequential (default). "
             "Positive values override to use exactly N workers. "
             "Auto-detects optimal dimension: texts vs patterns.",
    )

    # Diagnostics
    subparser.add_argument(
        "--discover-fails",
        type=str,
        metavar="FILE",
        help="Write patterns that failed to match to TSV file. "
             "Format: original_pattern<TAB>regex<TAB>expected_tinyIds. "
             "Useful for diagnosis of regex issues.",
    )
    subparser.add_argument(
        "--analyze-conflicts",
        type=str,
        metavar="FILE",
        help="Analysis mode: detect pattern containment conflicts that affect stripping order. "
             "Finds cases where pattern A is contained in pattern B, meaning order matters. "
             "Outputs TSV report with: short_pattern, long_pattern, relationship (prefix/suffix/interior), "
             "position, remainder, and recommendations. Exits after analysis (no discovery performed). "
             "Use to review patterns before stripping.",
    )
    subparser.add_argument(
        "--sort-order",
        choices=["length", "file", "alpha"],
        default="length",
        help="Pattern processing order for conflict analysis: 'length' (longest-first, default), "
             "'file' (preserve TSV file order), 'alpha' (alphabetical).",
    )

    # False-negative analysis
    subparser.add_argument(
        "--analyze-false-negatives",
        action="store_true",
        help="Analysis mode: analyze remaining 'as part of' patterns in -i/--input JSON. "
             "Extracts patterns not fully stripped, counts occurrences, suggests candidates "
             "for supplementary_patterns.yaml. Outputs report to --output (TSV format) "
             "and displays summary to terminal. Exits after analysis (no discovery performed).",
    )
    subparser.add_argument(
        "--fn-anchor",
        type=str,
        default="as part of",
        help="Anchor phrase to search for in false-negative analysis (default: 'as part of').",
    )

    # Supplementary pattern import
    subparser.add_argument(
        "--add-to-supplementary",
        type=str,
        metavar="CURATED_TSV",
        help="Import mode: add patterns from curated TSV to supplementary_patterns.yaml. "
             "TSV must have 'pattern' and 'name' columns. Optional 'acronym' column. "
             "Patterns are added to 'added_patterns' section. File is deleted after import. "
             "Use after reviewing --analyze-false-negatives output.",
    )
    subparser.add_argument(
        "--supplementary-section",
        type=str,
        default="added_patterns",
        help="YAML section name for imported patterns (default: 'added_patterns').",
    )

    # Merge utility
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

    # Coalesce utility (tinyId-aware subsumption)
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

    # Abbreviation discovery mode
    subparser.add_argument(
        "--discover-abbreviations",
        type=str,
        metavar="FILE",
        help="Discovery mode: extract abbreviations from instruments.tsv or instrument_families.tsv, "
             "then scan --input JSON for designation patterns using those abbreviations. "
             "Finds patterns like '[PROMIS]' (bracketed suffix) and 'PROMIS - ' (hyphen prefix). "
             "These patterns are often missed by k-mer mining due to short length or variant forms. "
             "Requires --input (CDE JSON) and --output (TSV). The --model flag is optional.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
