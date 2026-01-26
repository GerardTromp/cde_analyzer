import json
import logging
from logic.counter import count_matching_fields
from utils.output_writer import phrase_write_output
from utils.helpers import (
    safe_nested_increment,
    flatten_nested_dict,
    export_results_csv,
    export_results_tsv,
)
from utils.file_utils import exit_if_missing, graceful_interrupt
from argparse import ArgumentParser
from CDE_Schema import CDEItem

logger = logging.getLogger(__name__)

@graceful_interrupt
def run_action(args):
    input_path = exit_if_missing(args.input, "Input file")
    raw = json.load(open(input_path))
    items = [CDEItem.model_validate(obj) for obj in raw]

    results = count_matching_fields(
        items=items,
        field_names=args.fields,
        match_type=args.match_type,
        value_match=args.value,
        logic_expr=args.logic,
        group_by=args.group_by,
        group_type=args.group_type,
        # verbose=args.verbose, # verbosity moved to main script
        count_type=args.count_type,
        char_limit=args.char_limit,
    )
    # define shorter vars to avoid using arg.* in many places
    output_path = args.output
    output_flat = args.output_flat
    group_by = args.group_by

    if output_path:
        if output_flat:
            flattened = flatten_nested_dict(results)
            with open(output_path, "w", newline="") as f:
                json.dump(flattened, f, indent=2)
        elif output_path.endswith(".csv"):
            export_results_csv(results, output_path, group_by or "group")
        elif output_path.endswith(".tsv"):
            export_results_tsv(results, output_path, group_by or "group")
        else:
            with open(output_path, "w", newline="") as f:
                json.dump(results, f, indent=2)

    phrase_write_output(results, format=args.output_format, out_path=args.output)
    