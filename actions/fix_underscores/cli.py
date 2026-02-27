# actions/fix_underscores/cli.py

from argparse import ArgumentParser, BooleanOptionalAction

help_text = "Prepend a character to JSON keys starting with an underscore."


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action
description_text = "Pydantic reserves keys beginning with an underscore as private. Convert to start with another character."

def register_subparser(subparser: ArgumentParser):
    subparser.add_argument(
        "--input", "-i", required=True, help="Full path, including name, of input JSON file."
    )
    subparser.add_argument(
        "--output", "-o", help="Full path, including name, of output JSON file."
    )
    subparser.add_argument(
        "--prefix",
        required=False,
        default="x", 
        help="Character to prepend on fields starting with an underscore.",
    )
    subparser.add_argument(
        "--depth",
        type=int,
        help="Maximum depth (JSON nesting) to process. (type integer).",
    )
    subparser.set_defaults(
        _runner="actions.fix_underscores.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)