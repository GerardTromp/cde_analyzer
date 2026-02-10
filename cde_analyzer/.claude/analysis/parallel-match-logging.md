# Lessons Learned: Parallel Match Logging in strip_phrases

**Date**: 2026-02-06
**Feature**: `--match-log`, `--match-summary` with parallel worker support
**Files**: `logic/phrase_stripper.py`, `actions/strip_phrases/run.py`, `actions/strip_phrases/cli.py`

---

## Problem Statement

The `strip_phrases` action supports parallel processing via `--workers N` to speed up phrase stripping on large datasets. However, match logging (tracking which patterns matched which records) initially forced sequential processing because:

1. **Global state isn't shared**: Python's `ProcessPoolExecutor` creates separate process memory spaces
2. **Race conditions**: Multiple workers writing to a shared log file would cause interleaving/corruption
3. **Trace files**: The existing `--trace-matching` feature writes to a single file with detailed per-match output

The user requested a way to get pattern match counts (`--match-summary`) while still benefiting from parallel execution.

---

## Solution: Per-Worker Collection with Main Process Aggregation

Instead of temp files or shared state, the solution collects matches per-worker and aggregates in the main process after all workers complete.

### Key Design Decisions

1. **Trace files remain sequential-only**: The `--trace-matching` feature writes detailed per-match output to a single file. Parallelizing this would require temp files and merging, adding complexity for a diagnostic feature. It's simpler to force sequential mode when trace is enabled.

2. **Match logging is parallel-safe**: The new `--match-log` and `--match-summary` features only need the final aggregated data, not streaming output. Workers can collect matches in memory and return them alongside processed data.

3. **Worker return value extended**: `_worker_process_chunk()` now returns a 3-tuple: `(chunk_idx, processed_data, matches)` instead of `(chunk_idx, processed_data)`.

4. **Aggregation after completion**: The main process collects all matches from all workers and extends the global `_match_log` after parallel processing completes.

---

## Implementation Details

### Worker Initialization (`_worker_init`)

```python
def _worker_init(
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]],
    model_class_name: str,
    source_map: Optional[dict] = None,
    logging_enabled: bool = False
):
    global _phrase_map_global, _model_class_global, _source_map_global, _logging_enabled_global
    global _match_log, _source_map

    _phrase_map_global = phrase_map
    _model_class_global = MODEL_REGISTRY.get(model_class_name)
    _source_map_global = source_map or {}
    _logging_enabled_global = logging_enabled

    if logging_enabled:
        _match_log = []  # Fresh list for this worker
        _source_map = source_map or {}
```

### Worker Chunk Processing (`_worker_process_chunk`)

```python
def _worker_process_chunk(chunk_with_indices) -> Tuple[int, List[dict], List[dict]]:
    global _phrase_map_global, _logging_enabled_global, _match_log
    chunk_idx, data_list = chunk_with_indices

    if _logging_enabled_global:
        _match_log = []  # Reset for this chunk

    processed = []
    for data in data_list:
        processed_data = _strip_single_model(data, _phrase_map_global)
        processed.append(processed_data)

    # Return matches collected during this chunk
    matches = list(_match_log) if _logging_enabled_global and _match_log else []
    return chunk_idx, processed, matches
```

### Main Process Aggregation (`strip_phrases`)

```python
# Process in parallel
all_matches = []
with ProcessPoolExecutor(...) as executor:
    futures = {executor.submit(_worker_process_chunk, chunk): chunk[0] for chunk in chunks}

    for future in as_completed(futures):
        chunk_idx, processed_data, matches = future.result()
        results[chunk_idx] = processed_data
        if matches:
            all_matches.extend(matches)

# Aggregate into global match log
if logging_enabled and all_matches:
    if _match_log is None:
        _match_log = []
    _match_log.extend(all_matches)
    logger.info(f"Aggregated {len(all_matches)} match log entries from {n_workers} workers")
```

### Match Summary Generation (`write_match_summary`)

```python
def write_match_summary(match_log: list, filepath: str):
    """Aggregate match log entries into pattern-level counts."""
    from collections import Counter

    pattern_counts = Counter()
    pattern_tinyids = {}  # source_pattern -> set of tinyIds

    for entry in match_log:
        source = entry.get('source_pattern', entry.get('matched_pattern', ''))
        tinyid = entry.get('tinyId', '')
        pattern_counts[source] += 1
        if source not in pattern_tinyids:
            pattern_tinyids[source] = set()
        if tinyid:
            pattern_tinyids[source].add(tinyid)

    # Sort by count descending, write TSV
    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])
    # ... write to file
```

---

## CLI Changes

```bash
# New arguments in strip_phrases
--match-log FILE      # Detailed per-match TSV (tinyId, matched_pattern, source_pattern, verbatim_text)
--match-summary FILE  # Aggregated counts TSV (source_pattern, match_count, unique_records)
```

Both options now work with parallel execution. Only `--trace-matching` forces sequential mode.

---

## Testing Results

Test run on scheuermann10 dataset (1148 CDEs, 97 patterns, 4 workers):

| Mode | Records | Workers | Matches | Patterns | Time |
|------|---------|---------|---------|----------|------|
| Sequential | 1148 | 1 | 533 | 97 | baseline |
| Parallel | 1148 | 4 | 533 | 97 | ~2x faster |

**Verification**: Sorted comparison of match summaries showed identical data between sequential and parallel runs. Minor row ordering differences for patterns with equal counts were expected and harmless.

---

## Lessons for Future Development

### 1. Distinguish streaming vs batch output needs

- **Streaming** (trace files): Requires sequential processing or temp file merging
- **Batch** (match log/summary): Can aggregate after parallel completion

### 2. Worker return values are the aggregation mechanism

In `ProcessPoolExecutor`, workers can't write to shared memory. The cleanest solution is extending the return value to include any data that needs aggregation, rather than managing temp files.

### 3. Global state per-worker is isolated

Each worker gets its own copy of global variables after `fork()`. This is a feature, not a bug — it allows workers to maintain independent state that gets collected at the end.

### 4. Re-initialize worker state per chunk

Workers may be reused for multiple chunks. Always reset per-chunk state at the start of `_worker_process_chunk()` to avoid accumulating data from previous chunks.

### 5. Log aggregation for visibility

The line `logger.info(f"Aggregated {len(all_matches)} match log entries from {n_workers} workers")` provides confidence that parallel aggregation worked correctly. Include similar visibility logging for any parallel aggregation pattern.

---

## Related Files

- [logic/phrase_stripper.py](../../logic/phrase_stripper.py) - Core stripper with parallel support
- [actions/strip_phrases/run.py](../../actions/strip_phrases/run.py) - Action orchestration
- [actions/strip_phrases/cli.py](../../actions/strip_phrases/cli.py) - CLI arguments

---

## Future Enhancements

1. **Streaming match log with temp files**: If detailed streaming output is needed during parallel execution, implement temp file per worker with post-hoc merge.

2. **Progress callbacks**: Currently workers are silent. Could add a shared `multiprocessing.Queue` for progress updates without affecting the aggregation pattern.

3. **Memory optimization**: For very large datasets, could write matches to per-worker temp files instead of holding in memory, then merge at end.
