#
# File: actions/discovery_report/cli.py
#
"""
Discovery Report - Generate markdown summary reports for discovery pipelines.

Summarizes pipeline execution with per-step metrics (pattern counts, tinyId
coverage, subsumption stats) and optional sanity-check survivor census.

Supports both instrument detection and phrase stripping pipelines.
Preserves version history across iterations for tracking improvements.

Usage Examples:

  # Instrument pipeline report
  cde-analyzer discovery_report --output-dir phase1_output/ --pipeline instrument \\
      -o phase1_output/discovery_report.md

  # Phrase pipeline report
  cde-analyzer discovery_report --output-dir phase2_output/ --pipeline phrase \\
      -o phase2_output/discovery_report.md

  # With version label for iteration tracking
  cde-analyzer discovery_report --output-dir phase1_output/ --pipeline instrument \\
      --version iter-02 -o phase1_output/discovery_report.md
"""
from argparse import ArgumentParser

help_text = "Generate markdown summary reports for discovery pipelines"

description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    subparser.add_argument(
        "--output-dir", "-d",
        required=True,
        help="Pipeline output directory to scan for result files.",
    )
    subparser.add_argument(
        "--pipeline", "-p",
        required=True,
        choices=["instrument", "phrase"],
        help="Pipeline type: 'instrument' or 'phrase'.",
    )
    subparser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output markdown report.",
    )
    subparser.add_argument(
        "--version",
        help="Version label for iteration tracking (e.g., 'iter-01', 'baseline').",
    )
    subparser.add_argument(
        "--input-json", "-i",
        help="Original input JSON file (for record count in summary).",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
