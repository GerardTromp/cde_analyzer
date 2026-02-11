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
        nargs="+",
        metavar="FILE",
        help="Merge mode: read one or more curated TSV files, combine rows with "
             "identical patterns, merge their tinyId sets, and write deduplicated "
             "output to --output. Multiple files are concatenated before merging.",
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
    subparser.add_argument(
        "--no-trim-anchors",
        action="store_true",
        help="Disable anchor trimming during coalesce. By default, patterns containing "
             "anchor phrases ('as part of', 'based on', etc.) are trimmed to the bare "
             "instrument name, since discovery is intended to find patterns without anchors. "
             "Content preceding the anchor (CDE-specific text) is removed and tinyIds merged. "
             "Use this flag to preserve full anchor-containing patterns.",
    )
    subparser.add_argument(
        "--rollup-subset-tinyids",
        action="store_true",
        help="Enable tinyId-subset rollup during coalesce. After text-based subsumption, "
             "removes short patterns whose tinyIds are a strict subset of a longer pattern's "
             "tinyIds, even when the short pattern is not a text substring. "
             "Example: 'Score -' (1 tinyId) rolled up into 'CES-D total score' (5 tinyIds) "
             "because the tinyId set is fully covered. "
             "Only rolls up patterns that are shorter (by word count) than their covering pattern.",
    )

    subparser.add_argument(
        "--emit-def-variants",
        action="store_true",
        help="Emit definition-form variants during coalesce. For each pattern ending "
             "with ' -' (designation separator), also emits the pattern without it. "
             "Definitions use instrument names without trailing separators "
             "(e.g., '...Scale (CES-D).' vs '...Scale (CES-D) - question'). "
             "Without this flag, designation-only patterns miss definition matches.",
    )

    subparser.add_argument(
        "--split-tiers",
        type=int,
        metavar="MIN_TOKENS",
        default=0,
        help="Split coalesced output into two tiers by token count. "
             "Tier-1 (>=MIN_TOKENS tokens) written to --output. "
             "Tier-2 (<MIN_TOKENS tokens) written to {output_base}_short.tsv. "
             "Use with --coalesce-variants for two-pass stripping: "
             "strip long instrument patterns first, then short fragments. "
             "Default 0 = disabled (single output file).",
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
             "Use with --group-hierarchy. Default 0 = disabled.",
    )
    subparser.add_argument(
        "--min-tinyids-scale",
        type=float,
        default=0.0,
        help="Scale factor for adaptive tinyId threshold: "
             "effective_min = min_tinyids + floor(scale * sqrt(N)), where N is the "
             "total unique tinyIds (corpus size). Incidental groupings increase as "
             "sqrt(N), so this adjusts the noise floor proportionally. "
             "Use with --group-hierarchy. Default 0.0 = disabled (use fixed --min-tinyids only).",
    )

    # Generate strip pattern files from hierarchy
    subparser.add_argument(
        "--generate-strip-patterns",
        type=str,
        metavar="FILE",
        help="Generate strip-ready pattern files from a group-hierarchy TSV. "
             "Produces two files: {output}_full.tsv (full removal) and "
             "{output}_sub.tsv (group prefix removed, suffix retained). "
             "Both files are ready for use with strip_phrases --patterns.",
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
        help="Minimum patterns per semantic group (default: 2).",
    )
    subparser.add_argument(
        "--min-prefix-words",
        type=int,
        default=2,
        help="Minimum words in shared prefix to form a group (default: 2).",
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

    # Field analysis mode
    subparser.add_argument(
        "--field-analysis",
        type=str,
        metavar="FILE",
        help="Field analysis mode: enrich a patterns TSV with per-field tinyId counts. "
             "Adds def_count, desig_count, and field_profile columns by scanning the "
             "source JSON specified via --input. Requires --input and --model.",
    )
    subparser.add_argument(
        "--input", "-i",
        type=str,
        help="Path to CDE JSON file (required for --field-analysis).",
    )
    subparser.add_argument(
        "--model", "-m",
        type=str,
        default="CDE",
        help="Model type for parsing JSON (default: CDE). See MODEL_REGISTRY.",
    )
    subparser.add_argument(
        "--fields",
        type=str,
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to scan (default: definitions.*.definition designations.*.designation).",
    )
    subparser.add_argument(
        "--min-field-count",
        type=int,
        default=0,
        help="Filter: drop patterns below this count in BOTH fields. Default 0 = disabled.",
    )
    subparser.add_argument(
        "--min-tokens",
        type=int,
        default=0,
        help="Filter: drop patterns with fewer than N tokens. Default 0 = disabled.",
    )
    subparser.add_argument(
        "--exclude-patterns",
        type=str,
        metavar="FILE",
        help="Filter: remove patterns matching entries in this file (one per line or TSV with 'pattern' column).",
    )

    # Semantic proxy generation mode (wireframe)
    subparser.add_argument(
        "--generate-proxies",
        type=str,
        metavar="FILE",
        help="Generate semantic proxies for patterns using an LLM. "
             "Reads a patterns TSV (with pattern and tinyIds columns), "
             "looks up sample CDE contexts from --input JSON, queries the LLM "
             "for a 1-3 word semantic proxy per pattern, and writes an enriched "
             "TSV with replace_with and proxy_reasoning columns to --output. "
             "Requires --input, --model, and --provider.",
    )
    subparser.add_argument(
        "--provider",
        type=str,
        default="claude",
        choices=["claude", "openai", "google"],
        help="LLM provider for proxy generation (default: claude).",
    )
    subparser.add_argument(
        "--llm-model",
        type=str,
        help="LLM model identifier (e.g., claude-sonnet-4-20250514). "
             "Uses provider default if not specified.",
    )
    subparser.add_argument(
        "--config-file",
        type=str,
        help="Path to LLM config file (default: ~/.cde_analyzer/llm_config.json).",
    )
    subparser.add_argument(
        "--api-keys",
        nargs="+",
        help="API keys in format 'provider:key'.",
    )
    subparser.add_argument(
        "--context-window",
        type=int,
        default=150,
        help="Characters of surrounding text to include as context (default: 150).",
    )
    subparser.add_argument(
        "--max-contexts",
        type=int,
        default=3,
        help="Maximum CDE contexts to show per pattern (default: 3).",
    )
    subparser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show prompts without calling LLM (for debugging).",
    )

    # Normalize to minimal format
    subparser.add_argument(
        "--to-minimal",
        type=str,
        metavar="FILE",
        help="Normalize mode: extract pattern and tinyIds columns from any pattern TSV "
             "and write a minimal 2-column TSV (pattern, tinyIds) suitable for merging. "
             "Auto-detects column names (pattern/tinyIds/tinyids) and normalizes tinyId "
             "separator to pipe (|). Writes to --output.",
    )

    # Verbatim expansion mode
    subparser.add_argument(
        "--expand-verbatim",
        type=str,
        metavar="FILE",
        help="Expand curated patterns with temporal preposition, case, number, and plural variants. "
             "Reads a patterns TSV (with pattern and tinyIds columns), generates "
             "narrow verbatim variants (preposition swap, lowercase, digit↔word, day↔days), and "
             "writes expanded TSV to --output. Optionally re-scans source JSON "
             "with --rescan to discover tinyIds for each variant.",
    )
    subparser.add_argument(
        "--no-case-variants",
        dest="case_variants",
        action="store_false",
        default=True,
        help="Skip case variant generation (original + lowercase). Default: enabled.",
    )
    subparser.add_argument(
        "--no-number-variants",
        dest="number_variants",
        action="store_false",
        default=True,
        help="Skip digit↔word variants (7↔seven). Default: enabled.",
    )
    subparser.add_argument(
        "--no-plural-variants",
        dest="plural_variants",
        action="store_false",
        default=True,
        help="Skip singular↔plural variants (day↔days). Default: enabled.",
    )
    subparser.add_argument(
        "--no-temporal-variants",
        dest="temporal_variants",
        action="store_false",
        default=True,
        help="Skip temporal preposition variants (in/over/during/for/within × past/last). "
             "Default: enabled.",
    )
    subparser.add_argument(
        "--rescan",
        action="store_true",
        help="Re-scan source JSON to discover tinyIds for each expanded variant "
             "(instead of inheriting from source pattern). Requires --input and --model.",
    )

    # Interactive TSV editor mode
    subparser.add_argument(
        "--edit",
        type=str,
        metavar="FILE",
        help="Open an interactive TSV editor in the browser. "
             "Starts a local server, opens the browser pre-loaded with the TSV file, "
             "and supports save-back to disk. Press Ctrl-C to stop the server. "
             "Without a file, opens a blank editor for drag-drop loading.",
    )
    subparser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port for the editor server (default: auto-assign). Use with --edit.",
    )
    subparser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the editor server without opening a browser. Use with --edit.",
    )

    # YAML ↔ TSV conversion for supplementary patterns
    subparser.add_argument(
        "--yaml-to-tsv",
        type=str,
        metavar="YAML_FILE",
        help="Convert a supplementary_patterns.yaml to TSV for editing in the TSV editor. "
             "Output TSV has columns: section, pattern, name, acronym. "
             "Use with -o OUTPUT.tsv.",
    )
    subparser.add_argument(
        "--tsv-to-yaml",
        type=str,
        metavar="TSV_FILE",
        help="Convert an edited TSV back to supplementary_patterns.yaml format. "
             "TSV must have columns: section, pattern, name (acronym optional). "
             "Rows are grouped by section. Use with -o OUTPUT.yaml.",
    )

    # Harvest residuals mode
    subparser.add_argument(
        "--harvest-residuals",
        type=str,
        metavar="SANITY_TSV",
        help="Harvest residuals: cross-reference sanity check residuals against curated "
             "patterns. Classifies residuals as should_have_matched, partial_match, or "
             "new_candidate. Requires --curated and --output. Optionally uses --input "
             "and --model for field distribution.",
    )
    subparser.add_argument(
        "--curated",
        type=str,
        metavar="CURATED_TSV",
        help="Curated patterns TSV for residual harvesting (used with --harvest-residuals).",
    )

    # Pattern ledger mode
    subparser.add_argument(
        "--update-ledger",
        type=str,
        metavar="NEW_PATTERNS_TSV",
        help="Update pattern ledger: merge new patterns into a cumulative pattern registry. "
             "Tracks source, round, field_profile, and status across iterations. "
             "Requires --ledger and --output.",
    )
    subparser.add_argument(
        "--ledger",
        type=str,
        metavar="LEDGER_TSV",
        help="Path to existing ledger TSV (created if missing). Used with --update-ledger.",
    )
    subparser.add_argument(
        "--source",
        type=str,
        default="unknown",
        help="Source label for ledger entries (e.g., mined, harvested). Default: unknown.",
    )
    subparser.add_argument(
        "--round",
        type=int,
        default=1,
        help="Iteration round number for ledger entries. Default: 1.",
    )

    # Empirical subsumption validation mode
    subparser.add_argument(
        "--validate-subsumption",
        type=str,
        metavar="COALESCED_TSV",
        help="Empirical subsumption validation: for each coalesced group, check source "
             "text per-tinyId per-field to determine which patterns are actually needed. "
             "Drops shorter patterns that are always covered by longer group members. "
             "Requires --input, --model, and --output. Use --workers for parallelization.",
    )
    subparser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Number of parallel workers for validate-subsumption (0 = sequential). Default: 0.",
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

    # Harvest → local supplementary mode
    subparser.add_argument(
        "--harvest-to-supplementary",
        type=str,
        metavar="HARVEST_TSV",
        help="Convert harvest/sanity TSV patterns to supplementary YAML entries. "
             "Auto-generates name/acronym, deduplicates against global+local, "
             "and appends to ./supplementary_patterns.yaml (local override).",
    )

    # Promote local → global supplementary
    subparser.add_argument(
        "--promote-supplementary",
        action="store_true",
        help="Promote patterns from local ./supplementary_patterns.yaml into the "
             "global config/supplementary_patterns.yaml. Appends new entries "
             "preserving existing file structure. Use --clean-local to remove "
             "promoted patterns from the local file.",
    )
    subparser.add_argument(
        "--clean-local",
        action="store_true",
        help="Remove promoted patterns from local supplementary file "
             "(used with --promote-supplementary).",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
