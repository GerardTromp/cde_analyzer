#
# File: actions/subset/cli.py
#
from argparse import ArgumentParser, BooleanOptionalAction
from utils.constants import MODEL_REGISTRY

help_text = "Extract a subset of CDE records by tinyId"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action
description_text = """Filter CDE or Form records by a list of tinyIds and output
a smaller, schema-compliant JSON file. Useful for:
  - Creating focused datasets for specific analyses
  - Reducing file size for faster processing
  - Isolating records of interest from large CDE exports
"""


def register_subparser(subparser: ArgumentParser):
    # Input/Output
    subparser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input JSON file."
    )
    subparser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output file."
    )
    subparser.add_argument(
        "-m", "--model",
        required=True,
        choices=MODEL_REGISTRY.keys(),
        help="Pydantic model for validation (CDE, Form, EmbedText)."
    )
    subparser.add_argument(
        "--output-format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Output format (default: json)."
    )

    # tinyId filtering - file or CLI list
    subparser.add_argument(
        "--id-list",
        nargs="+",
        help="List of tinyIds to include or exclude."
    )
    subparser.add_argument(
        "--id-file",
        help="File containing tinyIds (JSON, CSV, or TSV)."
    )

    # Include/Exclude mode
    subparser.add_argument(
        "--exclude",
        action=BooleanOptionalAction,
        default=False,
        help="Exclude matching tinyIds (--exclude) or include them (--no-exclude, default)."
    )

    subparser.set_defaults(
        _runner="actions.subset.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)