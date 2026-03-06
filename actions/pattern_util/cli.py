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
from argparse import ArgumentParser, BooleanOptionalAction

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
        help="LLM provider for proxy generation.",
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
        help="Path to LLM config file (auto: ~/.cde_analyzer/llm_config.json).",
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
        help="Characters of surrounding text to include as context.",
    )
    subparser.add_argument(
        "--max-contexts",
        type=int,
        default=3,
        help="Maximum CDE contexts to show per pattern.",
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
        help="Port for the editor server. Use with --edit.",
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
        help="Source label for ledger entries (e.g., mined, harvested).",
    )
    subparser.add_argument(
        "--round",
        type=int,
        default=1,
        help="Iteration round number for ledger entries.",
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

    # Rare word detection mode
    subparser.add_argument(
        "--detect-rare-words", "-R",
        action="store_true",
        help="Detect rare words: scan CDE fields for single words that are frequent "
             "across CDEs but rare in general English (via wordfreq Zipf scores). "
             "ALL-CAPS words receive a penalty (likely acronyms, not common words). "
             "Outputs a curation TSV for review before stripping. "
             "Requires --input, --model, and --output.",
    )
    subparser.add_argument(
        "--zipf-threshold",
        type=float,
        default=1.5,
        help="Maximum effective Zipf score to be considered rare. "
             "Lower = stricter (fewer candidates). The Zipf scale is log10 of "
             "frequency per billion words: 0=absent, 3=uncommon, 5=common. "
             "Default: 1.5.",
    )
    subparser.add_argument(
        "--caps-penalty",
        type=float,
        default=2.5,
        help="Zipf penalty for ALL-CAPS words (len >= 2). Treats TOAST (3.96) as "
             "effectively 1.46, catching acronyms that spell common words. "
             "Default: 2.5.",
    )
    subparser.add_argument(
        "--rare-word-whitelist",
        type=str,
        metavar="YAML",
        help="Path to rare-word whitelist YAML. Words in this file are excluded "
             "from detection (legitimate domain terms). "
             "Default: auto-discovers config/rare_word_whitelist.yaml (global) "
             "and ./rare_word_whitelist.yaml (local override).",
    )
    subparser.add_argument(
        "--no-whitelist",
        action="store_true",
        help="Skip whitelist loading entirely (detect ALL rare words for comparison).",
    )
    # Note: --min-tinyids is already defined above (shared with group-hierarchy).
    # --input, --model, --output, --fields, --exclude-patterns are also shared.

    # Priority split mode (Zipf-based curation triage)
    subparser.add_argument(
        "--split-priority",
        type=str,
        metavar="FILE",
        help="Split a needs_review TSV into high-priority (domain-specific) and "
             "low-priority (common English) files using wordfreq Zipf scores. "
             "If ALL word tokens in a pattern have Zipf frequency >= threshold, "
             "the pattern is classified as low-priority (likely common English). "
             "Outputs: {stem}_high.tsv and {stem}_low.tsv. "
             "Use --zipf-threshold to control the cutoff (default: 4.0).",
    )
    subparser.add_argument(
        "--split-auto-remove",
        action="store_true",
        help="Pre-fill decision='remove' in low-priority patterns "
             "(used with --split-priority). Default: leave decision blank.",
    )

    # Remnant analysis diagnostic
    subparser.add_argument(
        "--remnant-analysis",
        type=str,
        metavar="FILE",
        help="Pre-strip diagnostic: simulate stripping patterns from CDE texts and "
             "identify frequent context words around each match. Reports extensions "
             "that suggest missing longer patterns (e.g. 'The free-text field' almost "
             "always followed by 'related to'). "
             "Requires --input (CDE JSON) and --output.",
    )
    subparser.add_argument(
        "--context-words",
        type=int,
        default=3,
        help="Number of context words to extract on each side of a pattern match. "
             "Used with --remnant-analysis. Default: 3.",
    )
    subparser.add_argument(
        "--min-context-freq",
        type=int,
        default=5,
        help="Minimum frequency for a context extension to be reported. "
             "Used with --remnant-analysis. Default: 5.",
    )

    # Parent-filtered recovery diagnostic (placeholder)
    subparser.add_argument(
        "--recover-parent-filtered",
        type=str,
        default=None,
        metavar="REPORT_TSV",
        help="[Diagnostic] Analyze parent-filtered patterns from a coalesce report "
             "for prefix recovery opportunities. Groups parent-filtered entries by "
             "word-level prefix and reports candidates with high divergence between "
             "actual tinyId count and parent_tinyid_count. "
             "Requires --output.",
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
        help="YAML section name for imported patterns.",
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

    # ──────────────────────────────────────────────────────────────
    # Multi-curator curation workflow
    # ──────────────────────────────────────────────────────────────

    subparser.add_argument(
        "--init-curation", "-C",
        type=str,
        metavar="FILE",
        help="Initialize multi-curator curation: create per-curator copies of a "
             "patterns TSV with added decision/modification/notes/curator columns. "
             "Each copy is named {stem}.{curator}.tsv. "
             "Requires --curators (comma-separated names). "
             "Use --output to set the output directory.",
    )
    subparser.add_argument(
        "--curators",
        type=str,
        help="Comma-separated list of curator names (e.g., 'alice,bob,carol'). "
             "Used with --init-curation to create per-curator copies.",
    )
    subparser.add_argument(
        "--merge-curation",
        nargs="+",
        metavar="FILE",
        help="Merge curated files from multiple curators and generate a consensus "
             "report. Accepts 2+ curator TSV files. Writes to --output directory: "
             "consensus.tsv (majority decisions), discrepancies.tsv (disagreements), "
             "inter_rater_report.md (statistics), discrepancies.html (visual diff). "
             "Row matching is by 'pattern' column (exact, case-sensitive).",
    )

    # ──────────────────────────────────────────────────────────────
    # Centralized curation server
    # ──────────────────────────────────────────────────────────────

    subparser.add_argument(
        "--serve-curation",
        type=str,
        metavar="CONFIG",
        help="Start a centralized curation server from a YAML config file "
             "(curators, TLS, timespan, output directory). "
             "Requires --curation-source to specify the patterns TSV. "
             "Each curator receives a unique token URL.",
    )
    subparser.add_argument(
        "--curation-source",
        type=str,
        metavar="FILE",
        help="Source patterns TSV for --serve-curation "
             "(e.g., coalesced_fields.tsv).",
    )
    subparser.add_argument(
        "--curation-status",
        type=str,
        metavar="DIR",
        help="Show status of a running or completed centralized curation session "
             "(reads .curation_state.yaml from the given directory).",
    )

    # ──────────────────────────────────────────────────────────────
    # Incremental curation (curation gate / finalize)
    # ──────────────────────────────────────────────────────────────

    subparser.add_argument(
        "--curation-gate",
        type=str,
        metavar="FILE",
        help="Curation gate: compare enriched patterns TSV against the curation "
             "ledger and classify patterns as auto-resolved or needs-review. "
             "Writes auto_resolved.tsv + needs_review.tsv (or curated.tsv if "
             "all patterns are auto-resolved). "
             "Requires --ledger-dir, --input, --model, --phase, and -o (directory).",
    )

    subparser.add_argument(
        "--finalize-curation",
        type=str,
        metavar="DIR",
        help="Finalize curation: merge auto-resolved patterns with human-curated "
             "needs_review.tsv to produce curated.tsv, then update the curation "
             "ledger. DIR is the output directory containing gate_result.json. "
             "Requires --ledger-dir, --input, and --phase.",
    )

    subparser.add_argument(
        "--ledger-dir",
        type=str,
        help="Path to curation ledger directory. Used with --curation-gate and "
             "--finalize-curation. Default: sibling of output dir named "
             "'.curation_ledger'.",
    )

    subparser.add_argument(
        "--phase",
        type=str,
        choices=["instrument", "phrase"],
        help="Pipeline phase for ledger operations (instrument = Phase 1, "
             "phrase = Phase 2). Used with --curation-gate and --finalize-curation.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
