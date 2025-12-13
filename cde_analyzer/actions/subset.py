#
# File: actions/subset.py
#
import argparse
import json
import pydantic
import sys
import logging
from typing import TypeVar
from pydantic import BaseModel
from CDE_Schema import CDEItem, CDEForm
from utils.helpers import extract_embed_project_fields_by_tinyid
from utils.tinyid_utils import load_tinyids
from utils.constants import MODEL_REGISTRY
from logic.extract_embed import extract_path
from argparse import ArgumentParser, ArgumentError, BooleanOptionalAction

# from actions.count import run_action
logger = logging.getLogger(__name__)

help_text = "Extract a subset of records that match some criteria on a pydantic path"
description_text = """Given a list of models (CDE, Form, ...) filter those that
match the search criteria and return a subset of the models
   
"""

models_str = ", ".join(MODEL_REGISTRY.keys())
