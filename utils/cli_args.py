"""
Shared CLI argument groups for consistent argument handling across actions.

This module provides reusable argument group functions that can be used
by action CLI modules to ensure consistent argument naming and behavior.
"""

from argparse import ArgumentParser, BooleanOptionalAction


def add_input_output_args(parser: ArgumentParser, input_required: bool = True):
    """
    Add standard input/output arguments to a parser.

    Args:
        parser: The ArgumentParser to add arguments to
        input_required: Whether the --input argument is required (default: True)

    Adds:
        --input, -i: Input JSON file path
        --output, -o: Output file path (optional, defaults to stdout)
        --output-format: Output format choice (json, csv, tsv)
    """
    parser.add_argument(
        "--input",
        "-i",
        required=input_required,
        help="Input JSON file path",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Output format (default: json)",
    )


def add_verbosity_args(parser: ArgumentParser):
    """
    Add standard verbosity and logging arguments to a parser.

    Args:
        parser: The ArgumentParser to add arguments to

    Adds:
        --verbosity, -v: Verbosity level (count action: -v, -vv, -vvv)
        --logfile: Optional log file path
    """
    parser.add_argument(
        "--verbosity",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity level (-v, -vv, -vvv for more debug output)",
    )
    parser.add_argument(
        "--logfile",
        help="Optional log file path",
    )


def add_model_arg(parser: ArgumentParser, required: bool = True):
    """
    Add the standard --model argument for Pydantic model selection.

    Args:
        parser: The ArgumentParser to add arguments to
        required: Whether the --model argument is required (default: True)

    Adds:
        --model, -m: Pydantic model choice from MODEL_REGISTRY
    """
    from utils.constants import MODEL_REGISTRY

    parser.add_argument(
        "--model",
        "-m",
        required=required,
        choices=MODEL_REGISTRY.keys(),
        help="Pydantic model to use for validation",
    )


def add_field_args(parser: ArgumentParser):
    """
    Add standard field selection arguments to a parser.

    Args:
        parser: The ArgumentParser to add arguments to

    Adds:
        --fields: List of field names to process
    """
    parser.add_argument(
        "--fields",
        nargs="+",
        required=True,
        help="List of field names to process",
    )


def add_match_args(parser: ArgumentParser):
    """
    Add standard matching arguments for field filtering.

    Args:
        parser: The ArgumentParser to add arguments to

    Adds:
        --match-type: Type of matching (non_null, null, fixed, regex)
        --value: Value to match if match-type is fixed or regex
    """
    parser.add_argument(
        "--match-type",
        choices=["non_null", "null", "fixed", "regex"],
        default="non_null",
        help="Type of match (null type is empty string/list or None)",
    )
    parser.add_argument(
        "--value",
        help="Value to match if match-type is fixed or regex",
    )


def add_pretty_print_args(parser: ArgumentParser):
    """
    Add pretty printing and formatting arguments.

    Args:
        parser: The ArgumentParser to add arguments to

    Adds:
        --pretty: Enable/disable pretty printing (BooleanOptionalAction)
        --set-keys: Include only set (non-null) keys in output
    """
    parser.add_argument(
        "--pretty",
        action=BooleanOptionalAction,
        default=True,
        help="Produce pretty (default: --pretty) or minified (--no-pretty) JSON",
    )
    parser.add_argument(
        "--set-keys",
        action=BooleanOptionalAction,
        default=True,
        help="Save model with only set keys (no null, None, or empty sets)",
    )


def add_dry_run_arg(parser: ArgumentParser):
    """
    Add a --dry-run argument for testing without side effects.

    Args:
        parser: The ArgumentParser to add arguments to

    Adds:
        --dry-run: Perform a dry run without writing output files
    """
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without writing output files",
    )
