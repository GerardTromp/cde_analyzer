#
# File: actions/supplementary/cli.py
#
"""
Supplementary pattern management and config utilities.

Manage supplementary pattern files and cross-format conversions:
- Import curated patterns into supplementary_patterns.yaml
- Harvest residuals from sanity checks
- Promote local supplementary patterns to global config
- Convert between YAML and TSV formats
- Update pattern ledgers across iterations

Usage Examples:

  # Add curated patterns to supplementary config
  cde-analyzer supplementary --add-to-supplementary curated.tsv

  # Convert YAML to TSV for editing
  cde-analyzer supplementary --yaml-to-tsv supplementary_patterns.yaml -o patterns.tsv

  # Harvest residuals from sanity check
  cde-analyzer supplementary --harvest-residuals sanity.tsv --curated curated.tsv -o harvest.tsv

  # Update iteration ledger
  cde-analyzer supplementary --update-ledger new_patterns.tsv --ledger ledger.tsv -o updated_ledger.tsv
"""
from argparse import ArgumentParser

help_text = "Supplementary pattern management (import, harvest, YAML/TSV conversion)"

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
        help="Path to CDE JSON file (for field distribution).",
    )
    subparser.add_argument(
        "--model", "-m",
        type=str,
        default="CDE",
        help="Model type for parsing JSON.",
    )

    # ──────────────────────────────────────────────────────────────
    # YAML ↔ TSV conversion for supplementary patterns
    # ──────────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────
    # Supplementary pattern import mode
    # ──────────────────────────────────────────────────────────────
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
    # Harvest residuals mode
    # ──────────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────
    # Pattern ledger mode
    # ──────────────────────────────────────────────────────────────
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
