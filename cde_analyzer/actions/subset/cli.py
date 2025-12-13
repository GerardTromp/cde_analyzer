#
# File: actions/subset/cli.py
#
from argparse import ArgumentParser, BooleanOptionalAction
from utils.constants import MODEL_REGISTRY

help_text = "Extract a subset of records that match some criteria on a pydantic path"
description_text = """Given a list of models (CDE, Form, ...) filter those that
match the search criteria and return a subset of the models
   
"""

def register_subparser(subparser: ArgumentParser):
    subparser.add_argument("--input", help="Input JSON file.")
    subparser.set_defaults(
        _runner="actions.phrase_builder.run"
    )