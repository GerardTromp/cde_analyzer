#
# File: actions/pattern_util/cli.py
#
"""
Pattern Util - Core TSV pattern manipulation utilities.

Provides utilities for working with pattern TSV files:
- Merge: Combine duplicate pattern rows, merging tinyIds
- Coalesce: Remove subsumed patterns (tinyId-aware subsumption)
- Field analysis: Enrich patterns with per-field tinyId counts
- Validate subsumption: Empirical per-field verification
- Expand: Verbatim and temporal seed variant generation
- Normalize: Convert to minimal 2-column format

Usage Examples:

  # Merge duplicate patterns
  cde-analyzer pattern_util --merge-patterns discovered.tsv -o merged.tsv

  # Coalesce patterns (remove subsumed)
  cde-analyzer pattern_util --coalesce-variants merged.tsv -o coalesced.tsv \\
      --min-prefix-tinyids 3 --coalesce-report report.tsv

  # Enrich with field counts
  cde-analyzer pattern_util --field-analysis coalesced.tsv -i cdes.json -o enriched.tsv

  # Expand temporal seeds
  cde-analyzer pattern_util --expand-temporal-seeds -o temporal_expanded.tsv

See also:
  cde-analyzer curation        — Editor, multi-curator, ledger, priority split
  cde-analyzer instrument_util — Group hierarchy, strip patterns, instrument splits
  cde-analyzer pattern_diag    — Rare words, remnant analysis, recovery
  cde-analyzer supplementary   — Import, harvest, YAML/TSV, ledger management
  cde-analyzer llm_classify    — LLM classification and semantic proxies
"""
from argparse import ArgumentParser, BooleanOptionalAction

help_text = "Core TSV pattern utilities (merge, coalesce, field analysis, expand)"

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
        "--merge-patterns", "-M",
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
        help="Column name for patterns in merge mode.",
    )
    subparser.add_argument(
        "--merge-tinyids-column",
        type=str,
        default="tinyIds",
        help="Column name for tinyIds in merge mode.",
    )

    # Coalesce mode (tinyId-aware subsumption)
    subparser.add_argument(
        "--coalesce-variants", "-c",
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
             "Use with --coalesce-variants. 0 = disabled.",
    )
    subparser.add_argument(
        "--min-parent-tinyids",
        type=int,
        default=0,
        help="Filter patterns by parent phrase tinyId count during coalesce. "
             "Drops patterns whose parent_tinyid_count < this threshold. "
             "Requires input TSV with parent_phrase and parent_tinyid_count columns "
             "(produced by strip_discover --parent-column). 0 = disabled.",
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
        "--defer-parent-filter",
        action=BooleanOptionalAction,
        default=False,
        help="Defer parent-tinyid filtering until after prefix extraction. "
             "Patterns rescued by a prefix group survive even if their individual "
             "parent count is below --min-parent-tinyids. Use for phrase pipelines "
             "where cross-parent aggregation matters. "
             "Use --no-defer-parent-filter to disable.",
    )

    subparser.add_argument(
        "--min-actual-tinyids",
        type=int,
        metavar="N",
        default=0,
        help="Protect patterns with >= N actual tinyIds from parent filtering "
             "regardless of parent_count. Prevents high-frequency verbatim "
             "boilerplate (e.g., 105 CDEs) from being lost when parent_count "
             "is 0 (dedup/verbatim origin). Default 0 = disabled. "
             "Recommended: 20 for phrase pipelines.",
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
             "0 = disabled (single output file).",
    )

    # Field analysis mode
    subparser.add_argument(
        "--field-analysis", "-A",
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
        "--min-field-count",
        type=int,
        default=0,
        help="Filter: drop patterns below this count in BOTH fields. 0 = disabled.",
    )
    subparser.add_argument(
        "--min-tokens",
        type=int,
        default=0,
        help="Filter: drop patterns with fewer than N tokens. 0 = disabled.",
    )
    subparser.add_argument(
        "--exclude-patterns",
        type=str,
        metavar="FILE",
        help="Filter: remove patterns matching entries in this file (one per line or TSV with 'pattern' column).",
    )
    subparser.add_argument(
        "--dedup-phrases",
        type=str,
        metavar="FILE",
        help="Filter: remove patterns that are substrings of dedup phrases in this TSV "
             "(dedup_phrases.tsv from phrase_miner). Prevents dedup fragments from cluttering curation.",
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
        "--expand-verbatim", "-e",
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
        help="Skip case variant generation (original + lowercase).",
    )
    subparser.add_argument(
        "--no-number-variants",
        dest="number_variants",
        action="store_false",
        default=True,
        help="Skip digit↔word variants (7↔seven).",
    )
    subparser.add_argument(
        "--no-plural-variants",
        dest="plural_variants",
        action="store_false",
        default=True,
        help="Skip singular↔plural variants (day↔days).",
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

    # Temporal seed expansion mode
    subparser.add_argument(
        "--expand-temporal-seeds", "-T",
        action="store_true",
        help="Expand temporal seed patterns from config/temporal_seed_patterns.yaml. "
             "Generates all preposition/tense/case/number/plural variants and writes "
             "a strip-ready TSV to --output.",
    )

    # Empirical subsumption validation mode
    subparser.add_argument(
        "--validate-subsumption", "-V",
        type=str,
        metavar="COALESCED_TSV",
        help="Empirical subsumption validation: for each coalesced group, check source "
             "text per-tinyId per-field to determine which patterns are actually needed. "
             "Drops shorter patterns that are always covered by longer group members. "
             "Requires --input, --model, and --output. Use --workers for parallelization.",
    )
    subparser.add_argument(
        "--workers", "-w",
        type=int,
        default=0,
        help="Number of parallel workers for validate-subsumption (0 = sequential).",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
