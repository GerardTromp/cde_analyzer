from argparse import ArgumentParser
from utils.constants import MODEL_REGISTRY

help_text = "Construct phrase models"
description_text = "Incremental phrase builder for CDE analysis"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


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

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)