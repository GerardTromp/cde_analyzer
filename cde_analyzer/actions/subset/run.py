#
# File: actions/subset/run.py
#
# Orchestration for the subset action
#

import json
import sys
import logging
from argparse import Namespace

from utils.file_utils import graceful_interrupt
from utils.tinyid_utils import load_tinyids
from utils.constants import MODEL_REGISTRY
from logic.subset import (
    subset_by_tinyids,
    subset_by_text,
    subset_by_pattern_file,
    write_subset_output,
    write_match_report,
    write_tinyid_report,
)

logger = logging.getLogger(__name__)


@graceful_interrupt
def run_action(args: Namespace):
    """
    Subset CDE records by tinyId list or text content.

    Validates input against the specified Pydantic model and outputs
    filtered records in the requested format.

    Two filtering modes:
        1. tinyId filtering: --id-list or --id-file
        2. Text filtering: --text-filter with --fields
    """
    # Determine filtering mode
    has_tinyid_filter = args.id_list or args.id_file
    has_text_filter = getattr(args, 'text_filter', None)
    has_pattern_file = getattr(args, 'pattern_file', None)

    # Count active filters
    filter_count = sum([bool(has_tinyid_filter), bool(has_text_filter), bool(has_pattern_file)])

    # Validate that we have exactly one filter
    if filter_count == 0:
        print(
            "error: One of --id-list/--id-file, --text-filter, or --pattern-file is required.",
            file=sys.stderr,
        )
        sys.exit(2)

    if filter_count > 1:
        print(
            "error: Cannot combine multiple filter modes. Use only one of: "
            "--id-list/--id-file, --text-filter, or --pattern-file.",
            file=sys.stderr,
        )
        sys.exit(2)

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

    mode = "exclude" if args.exclude else "include"

    # Initialize match_details for potential reports
    match_details = None

    if has_pattern_file:
        # Multi-pattern filtering from file (like grep -E -f)
        case_sensitive = getattr(args, 'case_sensitive', False)
        fields = getattr(args, 'fields', ['designation', 'definition'])

        logger.info(f"Pattern file filtering ({mode} mode): {args.pattern_file}")
        logger.info(f"  Fields: {fields}")
        if case_sensitive:
            logger.info("  Case-sensitive matching enabled")

        subset, matched_tinyids, match_details = subset_by_pattern_file(
            model_class=model_class,
            data=data,
            pattern_file=args.pattern_file,
            field_names=fields,
            exclude=args.exclude,
            case_sensitive=case_sensitive,
        )

        # Log pattern statistics
        n_patterns = len(set(d['pattern'] for d in match_details.values())) if match_details else 0
        n_labels = len(set(d['label'] for d in match_details.values() if d.get('label'))) if match_details else 0
        logger.info(f"Matched {len(matched_tinyids)} tinyIds against {n_patterns} patterns")
        if n_labels > 0:
            logger.info(f"  {n_labels} distinct labels (instrument families)")

        # Write optional reports
        match_report_path = getattr(args, 'match_report', None)
        if match_report_path and match_details:
            write_match_report(match_details, match_report_path)
            logger.info(f"Wrote match report to {match_report_path}")

        tinyid_report_path = getattr(args, 'tinyid_report', None)
        if tinyid_report_path and matched_tinyids:
            write_tinyid_report(matched_tinyids, tinyid_report_path)
            logger.info(f"Wrote tinyId report to {tinyid_report_path}")

    elif has_text_filter:
        # Text-based filtering
        case_sensitive = getattr(args, 'case_sensitive', False)
        use_regex = getattr(args, 'regex', False)
        fields = getattr(args, 'fields', ['designation', 'definition'])

        logger.info(f"Text filtering ({mode} mode): '{args.text_filter}' in fields {fields}")
        if case_sensitive:
            logger.info("  Case-sensitive matching enabled")
        if use_regex:
            logger.info("  Regex matching enabled")

        subset, matched_tinyids = subset_by_text(
            model_class=model_class,
            data=data,
            text_filter=args.text_filter,
            field_names=fields,
            exclude=args.exclude,
            case_sensitive=case_sensitive,
            use_regex=use_regex,
        )

        # Log matched tinyIds summary
        if matched_tinyids and len(matched_tinyids) <= 10:
            logger.info(f"Matched tinyIds: {', '.join(sorted(matched_tinyids))}")
        elif matched_tinyids:
            logger.info(f"Matched {len(matched_tinyids)} distinct tinyIds")

    else:
        # tinyId-based filtering
        if args.id_file:
            tinyids = load_tinyids(args.id_file)
            logger.info(f"Loaded {len(tinyids)} tinyIds from {args.id_file}")
        else:
            tinyids = args.id_list
            logger.info(f"Using {len(tinyids)} tinyIds from command line")

        logger.info(f"tinyId filtering ({mode} mode)")

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
