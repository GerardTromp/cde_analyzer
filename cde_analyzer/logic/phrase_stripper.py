import json
import csv
import re
import os
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, List, Tuple, Type, Optional, Set
from pydantic import BaseModel
from CDE_Schema import CDEItem, CDEForm
import logging
from utils.logger import log_if_verbose
from utils.analyzer_state import get_verbosity
from utils.extract_embed import sanitize
from utils.file_utils import require_file
from utils.flexible_pattern_matcher import get_optimal_workers

logger = logging.getLogger(__name__)
verbosity = get_verbosity()

# Module-level variable for sharing phrase_map with worker processes
_phrase_map_global: Optional[List[Tuple[str, str, str, Optional[Set[str]]]]] = None
_model_class_global: Optional[Type[BaseModel]] = None
_source_map_global: Optional[dict] = None
_logging_enabled_global: bool = False


# Modify to always expect replacement even if empty string
# def load_phrase_map(filepath: str) -> List[Tuple[str, str, str, Optional[Set[str]]]]:  # type: ignore
#     if filepath.endswith(".json"):
#         with open(filepath) as f:
#             data = json.load(f)
#         return [(item["path"], item["phrase"], item["replace"], set(item["tinyIds"])) for item in data]
#     else:
#         with open(filepath, newline="", encoding="utf-8") as f:
#             reader = csv.DictReader(
#                 f, delimiter="\t" if filepath.endswith(".tsv") else ","
#             )
#             for row in reader:
#                 # if row["tinyIds"] == "":
#                 #     return [(row["path"], row["phrase"], row["replace"],None)]
#                 # else: 
#                 #  Problem with 
#                 print(f"{row}")
#                 return [(row["path"], row["phrase"], row["replace"], row["tinyIds"]) for row in reader]  # type: ignore
def load_phrase_map(filepath: str) -> List[Tuple[str, str, str, Optional[Set[str]]]]:
    """
    Load phrase map from JSON or CSV/TSV file.

    Args:
        filepath: Path to phrase map file

    Returns:
        List of (path, phrase, replace, tinyIds) tuples

    Raises:
        FileNotFoundError: If file does not exist
    """
    require_file(filepath, "Phrase map file")

    if filepath.endswith(".json"):
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        phrase_map = []
        for item in data:
            path = item["path"]
            phrase = item["phrase"]
            replace = item.get("replace", "")  # force empty string if missing
            tiny_ids = item.get("tinyIds")
            tiny_ids_set = set(tiny_ids) if tiny_ids else None
            phrase_map.append((path, phrase, replace, tiny_ids_set))
        return phrase_map

    else:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(
                f, delimiter="\t" if filepath.endswith(".tsv") else ","
            )
            phrase_map = []
            for row in reader:
                path = row["path"]
                phrase = row["phrase"]
                replace = row.get("replace", "")
                tiny_ids = row.get("tinyIds")
                tiny_ids_set = set(tiny_ids.split()) if tiny_ids else None
                phrase_map.append((path, phrase, replace, tiny_ids_set))
            return phrase_map
        

def delete_phrase_at_path(obj: Any, path: str, phrase: str):
    """Delete a phrase from a string at the specified dotted path. Supports wildcards like field[*]."""
    logger.debug(f"Applying phrase '{phrase}' to path '{path}'")
    parts = re.split(r"\.(?![^\[]*\])", path)
    _navigate_and_strip(obj, parts, phrase)


def _navigate_and_strip(current: Any, parts: List[str], phrase: str):
    if not parts:
        return

    part = parts[0]
    # This should be re.search, the phrases might be within the text. 
    match = re.match(r"(\w+)(?:\[(\*|\d+)\])?", part)
    if not match:
        return
    key, index = match.group(1), match.group(2)

    if isinstance(current, dict):
        next_level = current.get(key)
        if next_level is None:
            return

        if index is None:
            if len(parts) == 1:
                _strip_in_place(current, key, phrase)
            else:
                _navigate_and_strip(next_level, parts[1:], phrase)
        elif index == "*":
            if isinstance(next_level, list):
                for item in next_level:
                    _navigate_and_strip(item, parts[1:], phrase)
        else:
            idx = int(index)
            if isinstance(next_level, list) and 0 <= idx < len(next_level):
                if len(parts) == 1:
                    _strip_in_place(next_level, idx, phrase)
                else:
                    _navigate_and_strip(next_level[idx], parts[1:], phrase)


def traverse_and_replace_phrase(
    obj: Any, path: str, phrase: str, replace_with: str = "",
    tiny_id: str = None
):
    """
    Traverse the object using a dot-separated path with support for wildcards (*)
    and replace the exact phrase (verbatim) in any matching string fields.

    Parameters:
        obj: The nested dict or list to modify in-place.
        path: A dot-separated path like "definitions.*.definition"
        phrase: The exact phrase to remove (must match exactly).
        replace_with: String to replace the phrase with (default: empty string).
        tiny_id: Optional tinyId for trace output.
    """
    parts = path.split(".")
    _recurse_and_replace(obj, parts, phrase, replace_with, tiny_id)


def _recurse_and_replace(
    current: Any, parts: List[str], phrase: str, replace_with: str,
    tiny_id: str = None
):
    if not parts:
        return

    key = parts[0]
    rest = parts[1:]

    if key == "*":
        if isinstance(current, list):
            for i, item in enumerate(current):
                _recurse_and_replace(item, rest, phrase, replace_with, tiny_id)
        else:
            logger.debug(f"Wildcard expected list but got {type(current).__name__}")
    elif isinstance(current, dict):
        if key in current:
            if not rest:
                _replace_if_match(current, key, phrase, replace_with, tiny_id)
            else:
                _recurse_and_replace(current[key], rest, phrase, replace_with, tiny_id)
        else:
            logger.debug(f"Key '{key}' not found in dict")
    elif isinstance(current, list):
        try:
            index = int(key)
            if index < len(current):
                if not rest:
                    _replace_if_match(current, index, phrase, replace_with, tiny_id)
                else:
                    _recurse_and_replace(current[index], rest, phrase, replace_with, tiny_id)
        except ValueError:
            logger.debug(f"Invalid index '{key}' for list")
    else:
        logger.debug(
            f"Cannot traverse non-collection type at {key}: {type(current).__name__}"
        )


# Module-level trace file for detailed matching diagnostics
_trace_file = None

# Module-level match log for full audit trail
_match_log: Optional[list] = None
_source_map: Optional[dict] = None


def set_trace_file(filepath: str):
    """
    Enable detailed matching trace output to a file.

    Args:
        filepath: Path to write trace output
    """
    global _trace_file
    _trace_file = open(filepath, 'w', encoding='utf-8')
    _trace_file.write("# Phrase Stripping Trace Log\n")
    _trace_file.write("# Format: MATCH|NO_MATCH tinyId phrase_len phrase[:50] [result]\n\n")


def close_trace_file():
    """Close the trace file if open."""
    global _trace_file
    if _trace_file:
        _trace_file.close()
        _trace_file = None


def init_match_log(source_map: Optional[dict] = None):
    """
    Initialize match logging for full audit trail.

    Args:
        source_map: Optional dict mapping expanded patterns to source patterns.
    """
    global _match_log, _source_map
    _match_log = []
    _source_map = source_map or {}


def get_match_log() -> list:
    """Return collected match log entries."""
    global _match_log
    return _match_log if _match_log else []


def write_match_log(filepath: str):
    """
    Write match log as TSV with header.

    Columns: tinyId, matched_pattern, source_pattern, verbatim_text
    """
    global _match_log
    if not _match_log:
        logger.warning("No match log entries to write")
        return

    import csv
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['tinyId', 'matched_pattern', 'source_pattern', 'verbatim_text'])
        for entry in _match_log:
            writer.writerow([
                entry.get('tinyId', ''),
                entry.get('matched_pattern', ''),
                entry.get('source_pattern', ''),
                entry.get('verbatim_text', ''),
            ])

    logger.info(f"Wrote {len(_match_log)} match log entries to {filepath}")


def close_match_log():
    """Clear match log state."""
    global _match_log, _source_map
    _match_log = None
    _source_map = None


def _replace_if_match(
    container: Any, key_or_index: Any, phrase: str, replace_with: str,
    tiny_id: str = None
):
    """
    Replace phrase in container at key_or_index if it exists.

    Args:
        container: Dict or list containing the value
        key_or_index: Key (for dict) or index (for list)
        phrase: Phrase to find and replace
        replace_with: Replacement string
        tiny_id: Optional tinyId for trace output
    """
    global _trace_file, _match_log, _source_map
    try:
        value = container[key_or_index]
        if isinstance(value, str):
            if phrase in value:
                log_if_verbose(f"Replacing phrase in path: {key_or_index}", 3)

                # Capture verbatim text (context around the match) before replacement
                idx = value.find(phrase)
                start = max(0, idx - 20)
                end = min(len(value), idx + len(phrase) + 20)
                verbatim = value[start:end]
                if start > 0:
                    verbatim = "..." + verbatim
                if end < len(value):
                    verbatim = verbatim + "..."

                result = sanitize(value.replace(phrase, replace_with))
                container[key_or_index] = result

                # Trace output for diagnosis
                if _trace_file:
                    phrase_preview = phrase[:50] + "..." if len(phrase) > 50 else phrase
                    _trace_file.write(f"MATCH\t{tiny_id or '-'}\t{len(phrase)}\t{phrase_preview}\n")

                # Match log for full audit trail
                if _match_log is not None:
                    source_pattern = _source_map.get(phrase, phrase) if _source_map else phrase
                    _match_log.append({
                        'tinyId': tiny_id or '',
                        'matched_pattern': phrase,
                        'source_pattern': source_pattern,
                        'verbatim_text': verbatim,
                    })
            else:
                log_if_verbose(f"Phrase not found at {key_or_index}", 3)
        else:
            logger.debug(f"Value at {key_or_index} is not a string: {value}")
    except Exception as e:
        logger.warning(f"Could not replace phrase at {key_or_index}: {e}")


def _strip_in_place(container: Any, key_or_index: Any, phrase: str):
    try:
        value = container[key_or_index]
        if not isinstance(value, str):
            logger.debug(f"Not a string at {key_or_index}: {value}")
            return
        if phrase not in value:
            logger.debug(f"Phrase '{phrase}' not found in: {value}")
            return

        new_value = value.replace(phrase, "")
        logger.info(f"Replacing phrase '{phrase}' in: {value}")
        container[key_or_index] = new_value

        # if new_value.strip() == "":
        #     logger.warning(f"Value became empty string after stripping: '{phrase}' at {key_or_index}")
        # value = container[key_or_index]
        # if isinstance(value, str) and phrase in value:
        #     new_value = value.replace(phrase, "")
        #     container[key_or_index] = new_value
        #     logger.info(f"Stripped phrase '{phrase}' at path -> {...}")
        #     if new_value.strip() == "":
        #         logger.warning(
        #             f"Empty string after stripping phrase '{phrase}' at path -> {...}"a
    except (KeyError, IndexError, TypeError):
        logger.error(f"Error stripping without index, key or type ")
        pass
    except Exception as e:
        logger.error(f"Error stripping at {key_or_index}: {e}")


def _strip_single_model(
    model_data: dict,
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]]
) -> dict:
    """
    Strip phrases from a single model's data dict.

    This is extracted to enable parallel processing.

    Args:
        model_data: Model data as dict (from model_dump)
        phrase_map: List of (path, phrase, replace, tinyIds) tuples

    Returns:
        Modified data dict with phrases stripped
    """
    tiny_id = model_data.get("tinyId")

    for path, phrase, replace_with, allowed_ids in phrase_map:
        if allowed_ids is not None and tiny_id not in allowed_ids:
            continue
        traverse_and_replace_phrase(model_data, path, phrase, replace_with, tiny_id)

    return model_data


# Debug counter for tinyId filtering diagnostics
_debug_filter_stats = {"checked": 0, "passed": 0, "sample_ids": set()}


def _strip_single_model_debug(
    model_data: dict,
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]]
) -> dict:
    """Debug version that tracks filter statistics."""
    global _debug_filter_stats
    tiny_id = model_data.get("tinyId")

    # Sample first 5 tinyIds for diagnostic
    if len(_debug_filter_stats["sample_ids"]) < 5 and tiny_id:
        _debug_filter_stats["sample_ids"].add(tiny_id)

    for path, phrase, replace_with, allowed_ids in phrase_map:
        _debug_filter_stats["checked"] += 1
        if allowed_ids is not None and tiny_id not in allowed_ids:
            continue
        _debug_filter_stats["passed"] += 1
        traverse_and_replace_phrase(model_data, path, phrase, replace_with, tiny_id)

    return model_data


def get_debug_filter_stats():
    """Return current debug filter statistics."""
    return _debug_filter_stats


def reset_debug_filter_stats():
    """Reset debug filter statistics."""
    global _debug_filter_stats
    _debug_filter_stats = {"checked": 0, "passed": 0, "sample_ids": set()}


def _worker_init(
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]],
    model_class_name: str,
    source_map: Optional[dict] = None,
    logging_enabled: bool = False
):
    """
    Initialize worker process with shared phrase_map.

    Uses global variables to avoid serializing large phrase_map for each task.
    """
    global _phrase_map_global, _model_class_global, _source_map_global, _logging_enabled_global
    global _match_log, _source_map
    _phrase_map_global = phrase_map

    # Resolve model class from name
    from utils.constants import MODEL_REGISTRY
    _model_class_global = MODEL_REGISTRY.get(model_class_name)

    # Set up logging state for this worker
    _source_map_global = source_map or {}
    _logging_enabled_global = logging_enabled
    if logging_enabled:
        # Initialize per-worker match log
        _match_log = []
        _source_map = source_map or {}


def _worker_process_chunk(chunk_with_indices: Tuple[int, List[dict]]) -> Tuple[int, List[dict], List[dict]]:
    """
    Process a chunk of model data dicts in a worker process.

    Args:
        chunk_with_indices: Tuple of (chunk_index, list of model data dicts)

    Returns:
        Tuple of (chunk_index, list of processed data dicts, list of match log entries)
    """
    global _phrase_map_global, _logging_enabled_global, _match_log
    chunk_idx, data_list = chunk_with_indices

    # Reset match log for this chunk (in case worker is reused)
    if _logging_enabled_global:
        _match_log = []

    processed = []
    for data in data_list:
        processed_data = _strip_single_model(data, _phrase_map_global)
        processed.append(processed_data)

    # Collect matches from this worker
    matches = list(_match_log) if _logging_enabled_global and _match_log else []

    return chunk_idx, processed, matches


def strip_phrases(
    model_list: List[BaseModel],
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]],
    n_workers: int = 1,
    source_map: Optional[dict] = None,
    logging_enabled: bool = False
) -> List[BaseModel]:
    """
    Strip phrases from a list of models.

    Args:
        model_list: List of Pydantic models to process
        phrase_map: List of (path, phrase, replace, tinyIds) tuples
        n_workers: Number of parallel workers (default: 1 for sequential)
                   Use 0 for auto-detect (CPU count)
        source_map: Optional dict mapping expanded patterns to source patterns.
                    Used for match logging in parallel mode.
        logging_enabled: If True, enable match logging (for parallel aggregation).

    Returns:
        List of cleaned models in original order
    """
    global _match_log

    if not model_list:
        return []

    # Get model class for reconstruction
    model_class = model_list[0].__class__
    model_class_name = None

    # Find model class name in registry for worker initialization
    from utils.constants import MODEL_REGISTRY
    for name, cls in MODEL_REGISTRY.items():
        if cls == model_class:
            model_class_name = name
            break

    # Convert models to dicts for processing
    model_data_list = [
        model.model_dump(mode="python", exclude_none=False)
        for model in model_list
    ]

    # Sequential processing (n_workers=1 or small dataset)
    if n_workers == 1 or len(model_list) < 100:
        cleaned_models = []
        for i, data in enumerate(model_data_list, 1):
            log_if_verbose(f"[strip_phrases] Processing model {i}/{len(model_list)}", 3)
            processed = _strip_single_model(data, phrase_map)
            cleaned = model_class.model_validate(processed)
            cleaned_models.append(cleaned)
        return cleaned_models

    # Parallel processing - resolve optimal worker count
    n_workers = get_optimal_workers(n_workers)

    # Don't use more workers than items
    n_workers = min(n_workers, len(model_list))

    # Split into chunks (one per worker)
    chunk_size = (len(model_data_list) + n_workers - 1) // n_workers
    chunks = []
    for i in range(0, len(model_data_list), chunk_size):
        chunk = model_data_list[i:i + chunk_size]
        chunks.append((len(chunks), chunk))

    logger.info(f"Parallel stripping: {len(model_list)} items across {n_workers} workers ({len(chunks)} chunks)")

    # Process in parallel
    results = {}
    all_matches = []
    with ProcessPoolExecutor(
        max_workers=n_workers,
        initializer=_worker_init,
        initargs=(phrase_map, model_class_name, source_map, logging_enabled)
    ) as executor:
        futures = {
            executor.submit(_worker_process_chunk, chunk): chunk[0]
            for chunk in chunks
        }

        for future in as_completed(futures):
            chunk_idx, processed_data, matches = future.result()
            results[chunk_idx] = processed_data
            if matches:
                all_matches.extend(matches)

    # Aggregate matches into global match log (if logging enabled)
    if logging_enabled and all_matches:
        if _match_log is None:
            _match_log = []
        _match_log.extend(all_matches)
        logger.info(f"Aggregated {len(all_matches)} match log entries from {n_workers} workers")

    # Reassemble in original order
    cleaned_models = []
    for chunk_idx in range(len(chunks)):
        processed_data_list = results[chunk_idx]
        for data in processed_data_list:
            cleaned = model_class.model_validate(data)
            cleaned_models.append(cleaned)

    return cleaned_models
