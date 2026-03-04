#
# File: actions/tsv_concat/run.py
#
"""
Orchestration for tsv_concat action.

Reads a multi-column TSV/CSV, concatenates selected columns with a separator,
and writes a 2-column TSV (id + concatenated text) for embedding models.
"""

import csv
import logging
from argparse import Namespace

from utils.file_utils import exit_if_missing, graceful_interrupt

logger = logging.getLogger(__name__)


def _detect_delimiter(path: str) -> str:
    """Detect delimiter from file extension."""
    return "," if path.lower().endswith(".csv") else "\t"


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for tsv_concat action."""
    from utils.pattern_tsv_utils import find_column_name

    input_path = exit_if_missing(args.input, "Input file")

    delimiter = _detect_delimiter(str(input_path))

    # Read input
    with open(input_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        headers = reader.fieldnames
        if not headers:
            logger.error("Input file has no headers")
            raise SystemExit(1)
        rows = list(reader)

    logger.info(f"Loaded {len(rows)} rows, {len(headers)} columns from {input_path}")

    # Resolve ID column
    id_col = find_column_name(headers, args.id_column)
    if id_col is None:
        logger.error(f"ID column '{args.id_column}' not found. "
                     f"Available: {', '.join(headers)}")
        raise SystemExit(1)

    # Determine which columns to concatenate
    non_id = [h for h in headers if h != id_col]

    if args.concat:
        # Whitelist: only specified columns
        concat_cols = []
        for name in args.concat:
            resolved = find_column_name(headers, name)
            if resolved is None:
                logger.error(f"Column '{name}' not found. "
                             f"Available: {', '.join(headers)}")
                raise SystemExit(1)
            if resolved == id_col:
                logger.warning(f"Skipping ID column '{resolved}' from concat list")
                continue
            concat_cols.append(resolved)
    elif args.drop:
        # Blacklist: all except dropped
        drop_set = set()
        for name in args.drop:
            resolved = find_column_name(headers, name)
            if resolved is None:
                logger.warning(f"Drop column '{name}' not found, ignoring")
                continue
            drop_set.add(resolved)
        concat_cols = [h for h in non_id if h not in drop_set]
    else:
        # Default: all non-ID columns
        concat_cols = non_id

    if not concat_cols:
        logger.error("No columns selected for concatenation")
        raise SystemExit(1)

    logger.info(f"ID column: {id_col}")
    logger.info(f"Concatenating {len(concat_cols)} columns: {', '.join(concat_cols)}")
    logger.info(f"Separator: {repr(args.separator)}")

    # Build output
    out_header = args.output_header
    output_rows = []
    skipped = 0

    for row in rows:
        parts = [str(row.get(col, "") or "") for col in concat_cols]
        text = args.separator.join(p for p in parts if p)

        if args.skip_empty and not text.strip():
            skipped += 1
            continue

        output_rows.append({id_col: row[id_col], out_header: text})

    if skipped:
        logger.info(f"Skipped {skipped} rows with empty text")

    # Write output TSV
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=[id_col, out_header], delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(output_rows)

    logger.info(f"Wrote {len(output_rows)} rows to {args.output}")
