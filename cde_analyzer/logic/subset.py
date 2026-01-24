#
# File: logic/subset.py
#
# Core logic for subsetting CDE records by tinyId
#

import csv
import json
import logging
from typing import Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)
ModelType = TypeVar("ModelType", bound=BaseModel)


def subset_by_tinyids(
    model_class: Type[ModelType],
    data: List[Dict],
    tinyids: List[str],
    exclude: bool = False,
) -> List[ModelType]:
    """
    Filter records by tinyId list with Pydantic validation.

    Args:
        model_class: Pydantic model class for validation
        data: List of raw dictionaries from JSON
        tinyids: List of tinyIds to filter on
        exclude: If True, exclude matching records; if False, include only matching

    Returns:
        List of validated Pydantic model instances

    Raises:
        ValidationError: If any record fails Pydantic validation
    """
    tinyid_set = set(tinyids)
    results: List[ModelType] = []
    validation_errors: List[Dict] = []

    for i, record in enumerate(data):
        # Extract tinyId from record
        record_tinyid = record.get("tinyId")
        if record_tinyid is None:
            logger.warning(f"Record {i} missing tinyId, skipping")
            continue

        # Apply filter logic
        in_set = record_tinyid in tinyid_set
        if exclude and in_set:
            continue
        if not exclude and not in_set:
            continue

        # Validate against Pydantic model
        try:
            validated = model_class.model_validate(record)
            results.append(validated)
        except ValidationError as e:
            validation_errors.append({
                "tinyId": record_tinyid,
                "index": i,
                "errors": e.errors(),
            })
            logger.error(f"Validation failed for tinyId={record_tinyid}: {e}")

    if validation_errors:
        logger.warning(
            f"Validation failed for {len(validation_errors)} records. "
            f"First error: {validation_errors[0]}"
        )

    logger.info(
        f"Subset complete: {len(results)} records "
        f"({'excluded' if exclude else 'included'} from {len(tinyids)} tinyIds)"
    )

    return results


def write_subset_output(
    records: List[ModelType],
    output_path: str,
    output_format: str = "json",
) -> None:
    """
    Write subset results to file in specified format.

    Args:
        records: List of Pydantic model instances
        output_path: Path to output file
        output_format: One of 'json', 'csv', 'tsv'
    """
    if not records:
        logger.warning("No records to write")
        return

    # Convert to dict for serialization
    rows = [record.model_dump() for record in records]

    if output_format == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)
    elif output_format == "csv":
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    elif output_format == "tsv":
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    logger.info(f"Wrote {len(records)} records to {output_path} ({output_format})")
