# actions/fix_underscores/cli.py

from argparse import ArgumentParser, BooleanOptionalAction

help_text = "Prepend a character to JSON keys starting with an underscore."
description_text = "Pydantic reserves keys beginning with an underscore as private. Convert to start with another character."

def register_subparser(subparser: ArgumentParser):
    subparser.add_argument(
        "--input", help="Full path, including name, of input JSON file."
    )
    subparser.add_argument(
        "--output", help="Full path, including name, of output JSON file."
    )
    subparser.add_argument(
        "--prefix",
        required=True,
        default="x", 
        help="Character to prepend on fields starting with an underscore.",
    )
    subparser.add_argument(
        "--depth",
        type=int,
        help="Maximum depth (JSON nesting) to process. (type integer).",
    )
    subparser.set_defaults(
        _runner="actions.phrase_builder.run"
    )
    # subparser.set_defaults(func=run_action)