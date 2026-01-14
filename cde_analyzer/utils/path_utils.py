# File: utils/path_utils.py

import csv
import json
from typing import Any, Dict, List, Union
from collections import defaultdict
from utils.logger import log_if_verbose


def load_path_schema(path: str) -> Dict[str, str]:
    """
    Load schema mapping output tags to dot-separated paths.
    Supports JSON, TSV, or CSV.
    """
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    schema = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t" if path.endswith(".tsv") else ",")
        for row in reader:
            tag = row.get("tag")
            path_expr = row.get("path")
            if tag and path_expr:
                schema[tag] = path_expr
    log_if_verbose(f"The schema dictionary is: {schema}", level=2)
    return schema


def get_path_value(obj: Any, path: str) -> Union[str, List[str], None]:
    """
    Get a value (or list of values) from nested object using a dot-separated path.
    Supports:
        - direct keys: a.b.c
        - list indexing: a.0.b
        - wildcards: a.*.b (returns list)
    """

    def resolve(part: str, context: Any) -> Any:
        if isinstance(context, list):
            try:
                return context[int(part)]
            except (ValueError, IndexError):
                return None
        if isinstance(context, dict):
            return context.get(part)
        return None

    parts = path.split(".")
    current: Any = obj

    for i, part in enumerate(parts):
        if part == "*":
            if not isinstance(current, list):
                return []
            remainder = ".".join(parts[i + 1 :])
            return [
                v
                for item in current
                for v in ([get_path_value(item, remainder)] if remainder else [item])
                if v is not None
            ]  # type: ignore
        else:
            current = resolve(part, current)
            if current is None:
                return None

    return current


def permis_values_to_dict_list(permisiblevalues: List[Dict]):
    """
    Converts a set of permissibleValue dictionaries
    with keys:
        codeSystemName, codeSystemVersion, permissibleValue, valueMeaningCode,
        valueMeaningDefinition, valueMeaningName, conceptId, conceptSource
    into a dictionary of lists, with the inner keys containing lists of
    values.
    )
    """
    dict_of_lists = defaultdict(list)

    for d in permisiblevalues:
        for key, value in d.items():
            dict_of_lists[key].append(value)

    return dict_of_lists
