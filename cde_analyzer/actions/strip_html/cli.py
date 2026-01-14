#
# File: actions/strip_html/cli.py
#
from argparse import ArgumentParser, BooleanOptionalAction
from utils.constants import MODEL_REGISTRY
from .run import run_action
    
help_text = "Clean (strip) embedded HTML from JSON structure"
description_text = "Clean and normalize string fields containing HTML in structured JSON via Pydantic models"


def register_subparser(subparser: ArgumentParser):
    subparser.add_argument(
        "--input", nargs="+", help="Input JSON file that has underscore tags fixed."
    )
    # subparser.add_argument(
    #     "--output", help="Path, including filename, to store results."
    # )
    subparser.add_argument(
        "--model",
        "-m",
        required=True,
        choices=MODEL_REGISTRY.keys(),
        help="Model to use for validation",
    )
    subparser.add_argument(
        "--outdir",
        default=".",
        help="Directory for output files (default: current directory)",
    )
    subparser.add_argument(
        "--output-format",
        choices=["json", "yaml", "csv"],
        default="json",
        help="Output format (default: json)",
    )
    subparser.add_argument(
        "--dry-run", action="store_true", help="Do not write output files"
    )
    subparser.add_argument(
        "--verbosity",
        "-v",
        action="count",
        default=1,
        help="Increase verbosity level (-vv for debug)",
    )
    subparser.add_argument("--logfile", help="Optional log file path")
    subparser.add_argument(
        "--pretty",
        action=BooleanOptionalAction,
        default=True,
        help="Produce pretty (default: --pretty) or minified (--no-pretty) JSON (no whitespace)",
    )
    subparser.add_argument(
        "--set-keys",
        action=BooleanOptionalAction,
        default=True,
        help="Save model with keys only represented if they are set (no null, None, or empty sets)",
    )
    subparser.add_argument(
        "--tables",
        action=BooleanOptionalAction,
        default=True,
        help="Convert html tables to JSON representation (default: --tables, i.e., true) or munged text (--no-tables)",
    )
    subparser.add_argument(
        "--colnames",
        action="store_true",
        default=False,
        help="Use first row of table as column names (default: false). Only relevant if --tables.",
    )
    subparser.set_defaults(
        _runner="actions.strip_html.run"
    )
    subparser.set_defaults(func=run_action)