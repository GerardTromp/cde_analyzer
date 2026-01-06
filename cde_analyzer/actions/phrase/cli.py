#
# File: actions/phrase/cli.py
#
from argparse import ArgumentParser, BooleanOptionalAction
from .run import run_action


help_text = "Extract common phrases from CDEs (Forms, not implemented yet)"
description_text = "Extract frequent phrases, verbatim or lemmatized, from designatted fields in CDE model classes"

def register_subparser(subparser: ArgumentParser):
    subparser.add_argument("--input", "-i", help="Input JSON file")
    subparser.add_argument(
        "--fields",
        "-f",
        nargs="+",
        required=True,
        help="Field names from pydantic classes",
    )
    subparser.add_argument(
        "--min-words",
        type=int,
        default=2,
        help="Minimum length of phrases, i.e., discard shorter phrases",
    )
    subparser.add_argument(
        "--min-ids",
        type=int,
        default=2,
        help="Minimum number of objects that share a phrase",
    )
    subparser.add_argument(
        "--remove-stopwords",
        action="store_true",
        help="Remove common English stop words (articles, prepositions, conjunctions)?",
    )
    subparser.add_argument(
        "--lemmatize",
        "-l",
        action=BooleanOptionalAction,
        default=True,
        help="Convert the text to standardized (lemma) form so that similar phrases match?",
    )
    subparser.add_argument(
        "--prune",
        "-p",
        type=str,
        choices=["none", "tinyid", "global", "threshold"],
        default="none",
        help="Collect longeset shared phrases. No, by tinyId, or globally",
    )
    subparser.add_argument(
        "--output-format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Choose output format",
    )
    subparser.add_argument(
        "--output", "-o", help="Path, including filename, to store results."
    )
    subparser.add_argument(
        "--verbatim",
        action="store_true",
        help="Include verbatim (non-lemmatized) phrases alongside lemma phrases",
    )
    subparser.set_defaults(
        _runner="actions.phrase.run"
    )
    subparser.set_defaults(func=run_action)

