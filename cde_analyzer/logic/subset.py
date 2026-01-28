#
# File: logic/subset.py
#
# Core logic for subsetting CDE records by tinyId or text content
#

import csv
import json
import logging
import re
from typing import Dict, List, Optional, Set, Tuple, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)
ModelType = TypeVar("ModelType", bound=BaseModel)


def extract_field_texts_from_dict(
    record: Dict,
    field_names: List[str],
) -> List[str]:
    """
    Extract text values from specified fields in a raw CDE dictionary.

    This is a lightweight extraction that works on raw dicts before Pydantic
    validation, enabling fast text filtering without full model instantiation.

    Args:
        record: Raw dictionary from JSON
        field_names: List of field names to extract (designation, definition, etc.)

    Returns:
        List of text strings found in the specified fields
    """
    texts = []

    # Designations (names, questions)
    if "designation" in field_names:
        designations = record.get("designations", [])
        if designations:
            for desig in designations:
                if isinstance(desig, dict) and desig.get("designation"):
                    texts.append(desig["designation"])

    # Definitions (descriptions)
    if "definition" in field_names:
        definitions = record.get("definitions", [])
        if definitions:
            for defn in definitions:
                if isinstance(defn, dict) and defn.get("definition"):
                    texts.append(defn["definition"])

    # Permissible value names
    if "valueMeaningName" in field_names:
        value_domain = record.get("valueDomain", {})
        if value_domain:
            perm_values = value_domain.get("permissibleValues", [])
            if perm_values:
                for pv in perm_values:
                    if isinstance(pv, dict) and pv.get("valueMeaningName"):
                        texts.append(pv["valueMeaningName"])

    # Permissible value definitions
    if "valueMeaningDefinition" in field_names:
        value_domain = record.get("valueDomain", {})
        if value_domain:
            perm_values = value_domain.get("permissibleValues", [])
            if perm_values:
                for pv in perm_values:
                    if isinstance(pv, dict) and pv.get("valueMeaningDefinition"):
                        texts.append(pv["valueMeaningDefinition"])

    return texts


def record_matches_text(
    record: Dict,
    text_filter: str,
    field_names: List[str],
    case_sensitive: bool = False,
    use_regex: bool = False,
) -> bool:
    """
    Check if a record contains the text filter in any of the specified fields.

    Args:
        record: Raw dictionary from JSON
        text_filter: Text pattern to search for
        field_names: Fields to search in
        case_sensitive: Whether to match case-sensitively
        use_regex: Whether to treat text_filter as a regex pattern

    Returns:
        True if the record matches the filter, False otherwise
    """
    texts = extract_field_texts_from_dict(record, field_names)

    if not texts:
        return False

    if use_regex:
        # Compile regex with appropriate flags
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(text_filter, flags)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{text_filter}': {e}")
            return False

        for text in texts:
            if pattern.search(text):
                return True
    else:
        # Simple substring match
        if not case_sensitive:
            text_filter_lower = text_filter.lower()
            for text in texts:
                if text_filter_lower in text.lower():
                    return True
        else:
            for text in texts:
                if text_filter in text:
                    return True

    return False


def subset_by_text(
    model_class: Type[ModelType],
    data: List[Dict],
    text_filter: str,
    field_names: List[str],
    exclude: bool = False,
    case_sensitive: bool = False,
    use_regex: bool = False,
) -> Tuple[List[ModelType], Set[str]]:
    """
    Filter records by text content in specified fields with Pydantic validation.

    This is a fast, grep-like filter that searches only in the specified fields,
    avoiding full document traversal. Useful for extracting subsets based on
    abbreviations, keywords, or patterns.

    Args:
        model_class: Pydantic model class for validation
        data: List of raw dictionaries from JSON
        text_filter: Text pattern to search for
        field_names: Fields to search in (designation, definition, etc.)
        exclude: If True, exclude matching records; if False, include only matching
        case_sensitive: Whether to match case-sensitively (default: False)
        use_regex: Whether to treat text_filter as a regex (default: False)

    Returns:
        Tuple of (list of validated Pydantic model instances, set of matched tinyIds)
    """
    results: List[ModelType] = []
    matched_tinyids: Set[str] = set()
    validation_errors: List[Dict] = []

    for i, record in enumerate(data):
        record_tinyid = record.get("tinyId", f"record_{i}")

        # Check if record matches text filter
        matches = record_matches_text(
            record, text_filter, field_names, case_sensitive, use_regex
        )

        # Apply filter logic
        if exclude and matches:
            continue
        if not exclude and not matches:
            continue

        # Record matches - validate against Pydantic model
        try:
            validated = model_class.model_validate(record)
            results.append(validated)
            matched_tinyids.add(record_tinyid)
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

    mode_str = "excluding" if exclude else "including"
    logger.info(
        f"Text filter complete: {len(results)} records "
        f"({mode_str} matches for '{text_filter}' in {field_names})"
    )

    return results, matched_tinyids


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
