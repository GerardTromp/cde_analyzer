from argparse import ArgumentParser
from utils.constants import MODEL_REGISTRY
from .run import run_action


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
        "-o", "--output", required=True, help="Path to output JSON file."
    )
    subparser.set_defaults(
        _runner="actions.phrase_builder.run"
    )
    subparser.set_defaults(func=run_action)