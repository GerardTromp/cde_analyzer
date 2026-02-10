# actions/fix_underscores.py

import json
import logging
from argparse import Namespace
from utils.file_utils import exit_if_missing, graceful_interrupt

logger = logging.getLogger(__name__)

def fix_keys(data, prefix, max_depth=None, current_depth=0):
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            new_key = key
            if key.startswith("_") and (
                max_depth is None or current_depth <= max_depth
            ):
                new_key = prefix + key
                logger.debug(
                    f"Renaming key: {key} -> {new_key} at depth {current_depth}"
                )
            new_dict[new_key] = fix_keys(value, prefix, max_depth, current_depth + 1)
        return new_dict
    elif isinstance(data, list):
        return [fix_keys(item, prefix, max_depth, current_depth) for item in data]
    else:
        return data


@graceful_interrupt
def run_action(args: Namespace):
    input_path = exit_if_missing(args.input, "Input file")
    logger.info(f"Reading input JSON from {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"Fixing underscore-prefixed keys with prefix '{args.prefix}'")
    fixed = fix_keys(data, args.prefix, args.depth)

    if args.output:
        logger.info(f"Writing output to {args.output}")
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            json.dump(fixed, f, indent=2)
    else:
        print(json.dumps(fixed, indent=2))
