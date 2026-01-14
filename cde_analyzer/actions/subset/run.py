#
# File: actions/subset/run.py
#

####################
# This is a stub that needs to be built out
####################

# import argparse
import json
# import pydantic
# import sys
import logging
#from typing import TypeVar
#from pydantic import BaseModel
# from utils.helpers import extract_embed_project_fields_by_tinyid
# from utils.tinyid_utils import load_tinyids
# from utils.constants import MODEL_REGISTRY
# from logic.extract_embed import extract_path
# from argparse import BooleanOptionalAction
from argparse import Namespace

# from actions.count import run_action
logger = logging.getLogger(__name__)

def run_action(args: Namespace):
    logger.info(f"Reading input JSON from {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    # logger.info(f"Fixing underscore-prefixed keys with prefix '{args.prefix}'")
    # fixed = fix_keys(data, args.prefix, args.depth)

    if args.output:
        logger.info(f"Writing output to {args.output}")
        # with open(args.output, "w", encoding="utf-8", newline="") as f:
        #     json.dump(fixed, f, indent=2)
    else:
        # print(json.dumps(fixed, indent=2))
        logger.info(f"Writing output to {args.output}")