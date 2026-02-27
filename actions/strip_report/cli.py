#
# File: actions/strip_report/cli.py
#
"""
Strip Report - Generate quality report for stripped JSON outputs.

Scans an output directory for stripped JSON files, runs remnant detection
on each, checks for remaining temporal phrases, and produces a markdown
summary with per-branch quality matrix.

Usage Examples:

  # Basic report for branching strip output
  cde-analyzer strip_report -d branching_output/ -o branching_output/strip_report.md

  # With input JSON baseline and version label
  cde-analyzer strip_report -d branching_output/ \\
      -i cdes_subset.json --version v2-temporal-fix \\
      -o branching_output/strip_report.md

  # Include embed CSV manifest
  cde-analyzer strip_report -d branching_output/ \\
      -i cdes_subset.json --embed-dir embed_data/ \\
      -o branching_output/strip_report.md

  # Custom JSON glob pattern
  cde-analyzer strip_report -d output/ --json-pattern "*.json" \\
      -o output/report.md
"""
from argparse import ArgumentParser

help_text = "Generate quality report for stripped JSON outputs"

description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    subparser.add_argument(
        "--output-dir", "-d",
        required=True,
        help="Directory containing *_stripped.json outputs.",
    )
    subparser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output markdown report.",
    )
    subparser.add_argument(
        "--input-json", "-i",
        help="Original input JSON file (for baseline record count).",
    )
    subparser.add_argument(
        "--version",
        help="Version label for iteration tracking (e.g., 'v2-temporal-fix').",
    )
    subparser.add_argument(
        "--embed-dir",
        help="Embed data directory for CSV file manifest.",
    )
    subparser.add_argument(
        "--no-temporal-scan",
        dest="temporal_scan",
        action="store_false",
        default=True,
        help="Skip scanning for remaining temporal phrases.",
    )
    subparser.add_argument(
        "--json-pattern",
        default="*_stripped.json",
        help="Glob pattern to match stripped JSON files in output-dir.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
