#
# File: actions/curation/cli.py
#
"""
Curation lifecycle management for pattern review.

Provides tools for the full curation workflow:
- Interactive TSV editor in the browser
- Multi-curator initialization, merge, and inter-rater statistics
- Centralized curation server with token-scoped routes
- Incremental curation gate and finalize (curation ledger)
- Zipf-based priority split for curation triage

Usage Examples:

  # Open interactive editor
  cde-analyzer curation --edit patterns.tsv

  # Initialize multi-curator curation
  cde-analyzer curation --init-curation enriched.tsv --curators alice,bob -o curation_dir/

  # Merge curator annotations
  cde-analyzer curation --merge-curation file.alice.tsv file.bob.tsv -o merged_dir/

  # Curation gate (incremental)
  cde-analyzer curation --curation-gate enriched.tsv --ledger-dir .curation_ledger \\
      --phase instrument -i cdes.json -o gate_dir/

  # Split by priority (Zipf triage)
  cde-analyzer curation --split-priority needs_review.tsv
"""
from argparse import ArgumentParser

help_text = "Curation lifecycle (editor, multi-curator, ledger, priority split)"

description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # ──────────────────────────────────────────────────────────────
    # Common args needed by multiple modes
    # ──────────────────────────────────────────────────────────────

    subparser.add_argument(
        "--output", "-o",
        help="Output path (file or directory, mode-dependent).",
    )
    subparser.add_argument(
        "--input", "-i",
        type=str,
        help="Path to CDE JSON file (required for --curation-gate).",
    )
    subparser.add_argument(
        "--model", "-m",
        type=str,
        default="CDE",
        help="Model type for parsing JSON. See MODEL_REGISTRY.",
    )

    # ──────────────────────────────────────────────────────────────
    # Interactive TSV editor
    # ──────────────────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────────────────
    # Priority split (Zipf-based curation triage)
    # ──────────────────────────────────────────────────────────────

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
        "--split-auto-skip",
        "--split-auto-remove",  # backwards-compatible alias
        action="store_true",
        dest="split_auto_remove",  # keep internal attr name for compat
        help="Pre-fill decision='skip' in low-priority patterns "
             "(used with --split-priority). Default: leave decision blank.",
    )
    subparser.add_argument(
        "--zipf-threshold",
        type=float,
        default=4.0,
        help="Zipf frequency threshold for --split-priority. Patterns where ALL "
             "word tokens have Zipf >= this value are classified as low-priority. "
             "Default: 4.0. Zipf reference: 3=uncommon, 4=common (~top 6K words), "
             "5=very common.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
