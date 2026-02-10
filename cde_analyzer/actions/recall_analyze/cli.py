#
# File: actions/recall_analyze/cli.py
#
# CLI for recall analysis and false-negative detection
#

from argparse import ArgumentParser
from utils.constants import MODEL_REGISTRY

help_text = "Analyze recall and detect false negatives in instrument detection"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


description_text = """Analyze instrument detection recall by comparing source data matches
against pipeline output. Identifies false negatives grouped by instrument family.

Use cases:
  - Verify recall of curated instrument patterns
  - Identify missing CDEs per instrument family
  - Support iterative threshold lowering with recall metrics
  - Generate grouped reports for efficient human curation

Workflow:
  1. Search source JSON for patterns (ground truth)
  2. Compare against pipeline output tinyIds
  3. Report recall metrics and false negatives by family
"""


def register_subparser(subparser: ArgumentParser):
    # Input files
    subparser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to source CDE JSON file (ground truth for pattern matching)."
    )
    subparser.add_argument(
        "-m", "--model",
        required=True,
        choices=MODEL_REGISTRY.keys(),
        help="Pydantic model for validation (CDE, Form, EmbedText)."
    )
    subparser.add_argument(
        "--pattern-file", "-F",
        required=True,
        help="File containing regex patterns with labels. "
             "Format: 'pattern<TAB>label' where label is the instrument family."
    )
    subparser.add_argument(
        "--pipeline-output",
        help="Pipeline output TSV file with tinyIds column (e.g., instruments.tsv). "
             "If omitted, only source matches are reported."
    )
    subparser.add_argument(
        "--pipeline-tinyid-column",
        default="tinyIds",
        help="Column name for tinyIds in pipeline output (default: tinyIds)."
    )

    # Output
    subparser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output recall report (TSV)."
    )
    subparser.add_argument(
        "--false-negatives-file",
        help="Optional: Output file listing false negative tinyIds by family."
    )
    subparser.add_argument(
        "--markdown-report",
        help="Path to output human-readable markdown report with summary and details."
    )
    subparser.add_argument(
        "--markdown-detail",
        help="Path to write a standalone detailed report for this phase only. "
             "Unlike --markdown-report (which is a rolling report with version history), "
             "this file captures the full per-family detail for one specific phase."
    )
    subparser.add_argument(
        "--report-version",
        help="Version label for this iteration (e.g., 'v1', 'iteration-2'). "
             "Used in version history tracking across multiple runs."
    )
    subparser.add_argument(
        "--report-title",
        default="Instrument Detection Recall Report",
        help="Title for the markdown report (default: 'Instrument Detection Recall Report')."
    )

    # Search options
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["designation", "definition"],
        help="Fields to search for patterns (default: designation definition)."
    )
    subparser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Make pattern matching case-sensitive (default: case-insensitive)."
    )

    # Recall threshold
    subparser.add_argument(
        "--min-recall",
        type=float,
        default=0.0,
        help="Minimum recall threshold to flag families needing attention (default: 0.0)."
    )

    # Iterative analysis / stopping criterion
    subparser.add_argument(
        "--previous-report",
        help="Previous recall report TSV for computing marginal gains. "
             "Used to track improvements across iterations."
    )
    subparser.add_argument(
        "--stopping-threshold",
        type=int,
        default=2,
        help="Stop iterating when marginal gain <= this value (default: 2). "
             "Reports when diminishing returns reached."
    )

    # Pattern suggestion
    subparser.add_argument(
        "--suggest-patterns",
        metavar="FILE",
        help="Output suggested patterns for families with recall < --min-recall threshold. "
             "Analyzes false negative designations to generate enhanced regex patterns. "
             "Format: pattern<TAB>suggested_label<TAB>matched_count<TAB>source_tinyIds. "
             "Requires --min-recall > 0 to identify underperforming families."
    )
    subparser.add_argument(
        "--suggest-min-matches",
        type=int,
        default=2,
        help="Minimum false negatives a suggested pattern must match (default: 2). "
             "Patterns matching fewer tinyIds are filtered out."
    )

    subparser.set_defaults(
        _runner="actions.recall_analyze.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
