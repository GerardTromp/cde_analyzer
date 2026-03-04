#
# File: actions/tsv_concat/cli.py
#
"""
TSV Concat - Selective column concatenation for embedding preparation.

Produces a 2-column TSV (id + concatenated text) from a multi-column TSV/CSV.

Example:
  cde-analyzer tsv_concat -i extract_output.tsv -o embed_input.tsv \\
      --concat definition designation -s " [SEP] "
"""
from argparse import ArgumentParser

help_text = "Concatenate TSV columns for embedding preparation"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    subparser.add_argument(
        "--input", "-i", required=True,
        help="Path to input TSV/CSV file.",
    )
    subparser.add_argument(
        "--output", "-o", required=True,
        help="Path to output 2-column TSV.",
    )
    subparser.add_argument(
        "--id-column",
        default="tinyId",
        help="Column to use as ID (default: tinyId).",
    )

    # Column selection (mutually exclusive)
    group = subparser.add_mutually_exclusive_group()
    group.add_argument(
        "--concat",
        nargs="+",
        metavar="COL",
        help="Columns to concatenate (whitelist). Others are dropped.",
    )
    group.add_argument(
        "--drop",
        nargs="+",
        metavar="COL",
        help="Columns to exclude (blacklist). Others are concatenated.",
    )

    subparser.add_argument(
        "--separator", "-s",
        default=" | ",
        help="Separator between concatenated values (default: ' | ').",
    )
    subparser.add_argument(
        "--output-header",
        default="embed_text",
        help="Header name for the concatenated column (default: embed_text).",
    )
    subparser.add_argument(
        "--skip-empty",
        action="store_true",
        help="Omit rows where concatenated text is empty.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
