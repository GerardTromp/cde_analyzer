#
# File: actions/subset/run.py
#
# Orchestration for the subset action
#

import json
import sys
import logging
from argparse import Namespace

from utils.tinyid_utils import load_tinyids
from utils.constants import MODEL_REGISTRY
from logic.subset import subset_by_tinyids, write_subset_output

logger = logging.getLogger(__name__)


def run_action(args: Namespace):
    """
    Subset CDE records by tinyId list.

    Validates input against the specified Pydantic model and outputs
    filtered records in the requested format.
    """
    # Validate that we have tinyIds from either source
    if not args.id_list and not args.id_file:
        print(
            "error: --id-list or --id-file is required.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Load tinyIds from file or CLI argument
    if args.id_file:
        tinyids = load_tinyids(args.id_file)
        logger.info(f"Loaded {len(tinyids)} tinyIds from {args.id_file}")
    else:
        tinyids = args.id_list
        logger.info(f"Using {len(tinyids)} tinyIds from command line")

    # Load input JSON
    logger.info(f"Reading input JSON from {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(
            "error: Input JSON must be a list of records.",
            file=sys.stderr,
        )
        sys.exit(2)

    logger.info(f"Loaded {len(data)} records from input")

    # Get model class from registry
    model_class = MODEL_REGISTRY[args.model]
    logger.info(f"Using model: {args.model} ({model_class.__name__})")

    # Perform subsetting with validation
    mode = "exclude" if args.exclude else "include"
    logger.info(f"Filtering records ({mode} mode)")

    subset = subset_by_tinyids(
        model_class=model_class,
        data=data,
        tinyids=tinyids,
        exclude=args.exclude,
    )

    # Write output
    logger.info(f"Writing {len(subset)} records to {args.output}")
    write_subset_output(
        records=subset,
        output_path=args.output,
        output_format=args.output_format,
    )

    print(f"Subset complete: {len(subset)} records written to {args.output}")
