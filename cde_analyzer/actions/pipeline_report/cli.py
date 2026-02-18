#
# File: actions/pipeline_report/cli.py
#
"""
Pipeline Report - Generate markdown summary reports for workflow execution.

Creates human-readable markdown reports summarizing pipeline progress:
- Phase completion status with step details
- Key metrics from output files (pattern counts, tinyId coverage)
- Recall analysis summary (if ground truth provided)
- Executive summary for stakeholders

Output format:
  - Markdown file with tables and sections
  - Version tracking for iteration history
  - Links to relevant output files

Usage:
  # Generate report from workflow state
  cde-analyzer pipeline_report --state-file output/.workflow_state.json -o report.md

  # Generate report for specific phase
  cde-analyzer pipeline_report --output-dir output/ --phase 2 -o phase2_report.md

  # Include recall analysis
  cde-analyzer pipeline_report --state-file output/.workflow_state.json \\
      --ground-truth patterns.txt --pipeline-output final_coalesced.tsv -o report.md
"""
from argparse import ArgumentParser

help_text = "Generate markdown summary reports for pipeline execution"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Input source (one required)
    input_group = subparser.add_argument_group("Input source (one required)")
    input_group.add_argument(
        "--state-file", "-s",
        help="Path to workflow state file (.workflow_state.json). "
             "Reads completed steps and output paths from workflow execution."
    )
    input_group.add_argument(
        "--output-dir", "-d",
        help="Path to pipeline output directory. "
             "Scans for known output files and generates metrics."
    )

    # Output
    subparser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output markdown report."
    )

    # Report options
    subparser.add_argument(
        "--phase", "-p",
        type=int,
        choices=[1, 2, 3, 4],
        help="Generate report for specific phase only (1-4). "
             "Without this, generates full pipeline report."
    )
    subparser.add_argument(
        "--title",
        default="Pipeline Execution Report",
        help="Title for the report (default: 'Pipeline Execution Report')."
    )
    subparser.add_argument(
        "--version",
        help="Version label for this report (e.g., 'v1', 'phase2-final'). "
             "Tracked in version history."
    )

    # Optional recall analysis
    recall_group = subparser.add_argument_group("Recall analysis (optional)")
    recall_group.add_argument(
        "--ground-truth", "-g",
        help="Ground truth pattern file for recall analysis. "
             "Format: pattern<TAB>label (one per line)."
    )
    recall_group.add_argument(
        "--pipeline-output",
        help="Pipeline output TSV for recall comparison. "
             "Uses final_coalesced.tsv by default if --state-file provided."
    )
    recall_group.add_argument(
        "--tinyid-column",
        default="tinyIds",
        help="Column name for tinyIds in pipeline output (default: tinyIds)."
    )
    recall_group.add_argument(
        "--source-json",
        help="Source CDE JSON file for recall analysis. "
             "Required if --ground-truth is provided."
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
