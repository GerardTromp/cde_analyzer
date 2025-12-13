#
# File: actions/extract_embed/cli.py
#
from argparse import ArgumentParser, BooleanOptionalAction
from utils.constants import MODEL_REGISTRY

def register_subparser(subparser: ArgumentParser):
    # parser = subparsers.add_parser(
    #     "strip_phrases",
    #     help="Remove curated phrases from specific paths in a JSON document.",
    # )
    subparser.add_argument(
        "-i", "--input", required=True, help="Path to input JSON file."
    )
    subparser.add_argument(
        "-m",
        "--model",
        choices=MODEL_REGISTRY.keys(),
        required=True,
        help="Top-level Pydantic model name for parsing the input JSON.",
    )
    subparser.add_argument(
        "-p",
        "--phrases",
        required=True,
        help="Path to phrases file (JSON, CSV, or TSV).",
    )
    subparser.add_argument(
        "-o", "--output", required=True, help="Path to output JSON file."
    )
    # subparser.add_argument(
    #     "-t", "--tids", required=True, help="Path to JSON file with list of tids."
    # )
    # This should be moved to post-processing. Inefficient and memory hungry
    subparser.add_argument(
        "-d",
        "--diff",
        action="store_true",
        help="Show diff between original and cleaned JSON",
    )
    subparser.add_argument(
        "--diff-output", type=str, help="Path to file for writing diff information."
    )
    subparser.add_argument(
        "-c", "--color", action="store_true", help="Colorize diff output."
    )
    subparser.add_argument(
        "--summary", action="store_true", help="Show a summary of lines changed lines."
    )
    subparser.add_argument(
        "-C",
        "--context",
        type=int,
        default=3,
        help="Number of context lines before and after changes.",
    )
    subparser.set_defaults(
        _runner="actions.phrase_builder.run"
    )
    # subparser.set_defaults(func=run_action)