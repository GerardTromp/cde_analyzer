import csv
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from utils.logger import log_if_verbose
from utils.file_utils import require_file


id_columnname_mapping = {
    "ID": "tinyId",
    "Id": "tinyId",
    "tinyID": "tinyId",
    "IDs": "tinyId",
    "Ids": "tinyId",
    # ... and so on
}


def parse_path_with_column(path_spec: str) -> Tuple[str, Optional[str]]:
    """
    Parse a path specification that may include a column specifier.

    Formats supported:
        - "file.csv" -> ("file.csv", None)
        - "file.csv:column_name" -> ("file.csv", "column_name")
        - "C:\\path\\file.csv:column_name" -> ("C:\\path\\file.csv", "column_name")
        - "/path/file.csv:column_name" -> ("/path/file.csv", "column_name")

    The column specifier is the part after the last colon, but only if:
        - It doesn't look like a Windows drive letter (single letter before colon)
        - The colon is not immediately after a path separator

    Returns:
        Tuple of (file_path, column_name or None)
    """
    # Find the last colon
    last_colon = path_spec.rfind(':')

    if last_colon == -1:
        # No colon at all
        return (path_spec, None)

    # Check if it's a Windows drive letter (e.g., "C:")
    # Drive letter is: single letter followed by colon at position 1
    if last_colon == 1 and path_spec[0].isalpha():
        return (path_spec, None)

    # Check if the part after the colon looks like a column name
    # (not a path continuation like "C:\path")
    after_colon = path_spec[last_colon + 1:]
    before_colon = path_spec[:last_colon]

    # If there's a backslash or slash right after the colon, it's a path continuation
    if after_colon and (after_colon[0] in '/\\'):
        return (path_spec, None)

    # If the part after the colon is empty, no column specified
    if not after_colon:
        return (path_spec, None)

    # If before_colon ends with a file extension, treat after_colon as column name
    # Common extensions: .csv, .tsv, .txt
    if re.search(r'\.(csv|tsv|txt)$', before_colon, re.IGNORECASE):
        return (before_colon, after_colon)

    # Otherwise, no column specified
    return (path_spec, None)


def parse_multi_tinyids(value: str) -> List[str]:
    """
    Parse a cell value that may contain multiple tinyIds.

    Handles:
        - Single tinyId: "abc123"
        - Pipe-separated (TSV style): "abc123|def456|ghi789"
        - Comma-separated: "abc123,def456,ghi789"
        - Space-separated: "abc123 def456 ghi789"

    Returns:
        List of individual tinyIds (stripped of whitespace, empty strings removed)
    """
    if not value:
        return []

    # Split on pipe, comma, or whitespace
    # Order matters: try pipe first (common in TSV), then comma, then space
    if '|' in value:
        parts = value.split('|')
    elif ',' in value:
        parts = value.split(',')
    else:
        parts = value.split()

    # Strip whitespace and filter empty strings
    return [p.strip() for p in parts if p.strip()]


def load_tinyids(path_spec: str) -> List[str]:
    """
    Load a set of tinyIds for inclusion or exclusion during processing.

    Supports JSON, TSV, or CSV with flexible column specification.

    Path formats:
        - "file.csv" - Uses default column detection (tinyId, ID, Id, etc.)
        - "file.csv:column_name" - Uses specified column

    File formats:
        1. JSON: key:value dictionary where value is list of tinyId
        2. CSV/TSV: Tabular data with tinyId column

    Multi-value cells:
        Cells can contain multiple tinyIds separated by:
        - Pipe: "abc|def|ghi"
        - Comma: "abc,def,ghi"
        - Space: "abc def ghi"

    Default column detection:
        Without explicit column, looks for: tinyId, ID, Id, tinyID, IDs, Ids

    Examples:
        load_tinyids("data.tsv")                    # Auto-detect tinyId column
        load_tinyids("data.csv:tinyId")             # Explicit column
        load_tinyids("curated_domains.csv:tinyId")  # Custom file with column

    Args:
        path_spec: File path, optionally with :column_name suffix

    Returns:
        List of tinyIds (deduplicated, order preserved)

    Raises:
        FileNotFoundError: If the file does not exist
        KeyError: If specified column not found in file
    """
    path, column_name = parse_path_with_column(path_spec)
    require_file(path, "ID file")

    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return json.load(f)["tinyId"]

    id_list = []
    seen = set()  # Track seen IDs for deduplication

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t" if path.endswith(".tsv") else ",")

        # Determine which column to use
        if column_name:
            # Explicit column specified
            target_column = column_name
        else:
            # Auto-detect: look for mapped column names or 'tinyId'
            target_column = None
            if reader.fieldnames:
                for col in reader.fieldnames:
                    if col in id_columnname_mapping:
                        target_column = col
                        break
                    elif col == "tinyId":
                        target_column = col
                        break

            if target_column is None:
                # Fall back to first column if nothing matches
                if reader.fieldnames:
                    target_column = reader.fieldnames[0]
                else:
                    raise KeyError("No columns found in file")

        for row in reader:
            if target_column not in row:
                raise KeyError(
                    f"Column '{target_column}' not found in file. "
                    f"Available columns: {list(row.keys())}"
                )

            cell_value = row[target_column]
            tinyids = parse_multi_tinyids(cell_value)

            for tid in tinyids:
                if tid not in seen:
                    seen.add(tid)
                    id_list.append(tid)
                    log_if_verbose(f"Added tinyId: {tid}", level=2)

    log_if_verbose(f"Loaded {len(id_list)} unique tinyIds from {path}", level=1)
    return id_list
