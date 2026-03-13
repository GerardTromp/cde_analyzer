#
# File: actions/pattern_diag/cli.py
#
"""
Pattern diagnostics and quality checks.

Pre-strip and post-strip diagnostic tools:
- Rare word detection using wordfreq Zipf scores
- Remnant analysis: simulate stripping to identify missed extensions
- Parent-filtered pattern recovery analysis

Usage Examples:

  # Detect rare words in CDE fields
  cde-analyzer pattern_diag --detect-rare-words -i cdes.json -o rare_words.tsv

  # Analyze remnants (pre-strip diagnostic)
  cde-analyzer pattern_diag --remnant-analysis patterns.tsv -i cdes.json -o remnants.tsv

  # Recover parent-filtered patterns
  cde-analyzer pattern_diag --recover-parent-filtered coalesce_report.tsv -o recovery.tsv
"""
from argparse import ArgumentParser

help_text = "Pattern diagnostics (rare words, remnant analysis, recovery)"

description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Common arguments
    subparser.add_argument(
        "--output", "-o",
        help="Output path for diagnostic results.",
    )
    subparser.add_argument(
        "--input", "-i",
        type=str,
        help="Path to CDE JSON file.",
    )
    subparser.add_argument(
        "--model", "-m",
        type=str,
        default="CDE",
        help="Model type for parsing JSON.",
    )
    subparser.add_argument(
        "--fields",
        type=str,
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to scan.",
    )
    subparser.add_argument(
        "--min-tinyids",
        type=int,
        default=0,
        help="Minimum tinyId count for rare word detection. 0 = disabled.",
    )
    subparser.add_argument(
        "--exclude-patterns",
        type=str,
        metavar="FILE",
        help="File of patterns to exclude from analysis.",
    )

    # ── Rare word detection mode ──────────────────────────────────
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

    # ── Remnant analysis diagnostic ───────────────────────────────
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

    # ── Parent-filtered recovery diagnostic ───────────────────────
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
