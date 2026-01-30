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

Related Commands:
- strip_analyze: Pattern conflict and false-negative analysis
- pattern_util: TSV utilities (merge, coalesce, supplementary import)
- strip_phrases: Apply stripping with curated patterns

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
    # Core arguments (required for discovery mode)
    subparser.add_argument(
        "--input", "-i", help="Path to input JSON file (CDE records)."
    )
    subparser.add_argument(
        "--model",
        "-m",
        choices=MODEL_REGISTRY.keys(),
        help="Top-level Pydantic model name for parsing the input JSON.",
    )
    subparser.add_argument(
        "--output", "-o", help="Path to output TSV file."
    )

    # Pattern source (required for discovery mode)
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
             "(default: definitions.*.definition designations.*.designation). "
             "Also supports: valueDomain.permissibleValues.*.valueMeaningName, "
             "valueDomain.permissibleValues.*.valueMeaningDefinition",
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
        "--min-bare-words",
        type=int,
        default=2,
        help="Minimum word count for bare instrument names (default: 2). "
             "Filters out short fragments like 'Score' that produce false positives "
             "during bare-name discovery. Only applies with --discover-bare-names.",
    )
    subparser.add_argument(
        "--allow-abbrev-variants",
        action="store_true",
        help="Enable abbreviation variant matching in flexible regex. "
             "Patterns like '(PHQ)' will also match '(PHQ-9)', '(PHQ-15)', etc. "
             "Useful for instruments with numbered variants.",
    )
    subparser.add_argument(
        "--allow-embedded-abbrev",
        action="store_true",
        help="Allow embedded abbreviation parentheticals between words. "
             "Patterns like 'Scale Long' will match 'Scale (GDS) Long'. "
             "Useful for instruments where abbreviations are inserted mid-name.",
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
             "Use 0 for auto-detect with headroom (n-1 CPUs for <=10 cores, n-2 for >10). "
             "Use 1 for sequential (default). "
             "Positive values override to use exactly N workers. "
             "Auto-detects optimal dimension: texts vs patterns.",
    )

    # Parent phrase tracking
    subparser.add_argument(
        "--parent-column",
        type=str,
        metavar="COLUMN",
        help="Column name in --pattern-list TSV that contains the parent (generic) phrase. "
             "When set, discovered.tsv will include 'parent_phrase' and 'parent_tinyid_count' "
             "columns. The parent tinyId count is aggregated across all verbatim variants "
             "sharing the same parent. Use with phrase_pipeline to track which generic phrase "
             "generated each verbatim pattern (e.g., --parent-column lemma_text).",
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

    # Abbreviation discovery mode
    subparser.add_argument(
        "--discover-abbreviations",
        type=str,
        metavar="FILE",
        help="Discovery mode: extract abbreviations from instruments.tsv or instrument_families.tsv, "
             "then scan --input JSON for designation patterns using those abbreviations. "
             "Finds patterns like '[PROMIS]' (bracketed suffix) and 'PROMIS - ' (hyphen prefix). "
             "For hyphen patterns, extracts common prefix patterns (e.g., 'PROMIS - Pain Interference') "
             "rather than full designations. Use --min-pattern-tinyids to filter by document support. "
             "Requires --input (CDE JSON) and --output (TSV). The --model flag is optional.",
    )
    subparser.add_argument(
        "--min-pattern-tinyids",
        type=int,
        default=2,
        help="Minimum tinyIds for abbreviation prefix patterns to be output (default: 2). "
             "Patterns with fewer tinyIds are filtered out. Use with --discover-abbreviations.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
