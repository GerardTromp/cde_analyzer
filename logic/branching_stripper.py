"""
N-way branching strip engine.

Produces all requested strip variants in a single pass over the CDE data.
Instead of the 13-step branching_strip.yaml pipeline that loads/parses the
22K-CDE JSON file 12 times, this engine loads JSON once and computes all
6 variants per CDE simultaneously.

Variant dependency graph::

              ┌─ MTSFPF (inst_full only)
              │
    original ─┼─ MFSTPF (inst_sub only)
              │
              ├─ inst_full ─┬─ MTSFPT (+ temporal + phrase)
              │             │
              │             └─ inst_sub ─── MTSTPT (+ temporal + phrase)
              │
              ├─ inst_sub ──── MFSTPT (+ temporal + phrase)
              │
              └─ temporal ──── MFSFPT (+ phrase)

Each variant is computed by chaining the required stages on a deep copy
of the original CDE dict.
"""

import copy
import json
import logging
import re
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.flexible_pattern_matcher import get_optimal_workers

logger = logging.getLogger(__name__)

# ── Variant definitions ──────────────────────────────────────────────────

# Which stages each variant needs, in application order.
# Stages: inst_full, inst_sub, temporal, phrase
VARIANT_STAGES: Dict[str, List[str]] = {
    "MTSFPF": ["inst_full"],
    "MFSTPF": ["inst_sub"],
    "MFSFPT": ["temporal", "phrase"],
    "MTSFPT": ["inst_full", "temporal", "phrase"],
    "MFSTPT": ["inst_sub", "temporal", "phrase"],
    "MTSTPT": ["inst_full", "inst_sub", "temporal", "phrase"],
}

ALL_VARIANT_CODES = list(VARIANT_STAGES.keys())


@dataclass
class StripStage:
    """Configuration for one stripping stage (e.g. instrument-full, temporal, phrase)."""

    name: str
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]]
    case_insensitive: bool = False
    word_boundary: bool = False
    compiled_cache: Optional[dict] = field(default=None, repr=False)

    def compile(self):
        """Pre-compile regex patterns (call once, reuse across CDEs)."""
        self.compiled_cache = _compile_pattern_cache(
            self.phrase_map, self.word_boundary, self.case_insensitive
        )


# ── Pattern compilation (mirrors phrase_stripper._compile_pattern_cache) ──

def _compile_pattern_cache(
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]],
    word_boundary: bool,
    case_insensitive: bool,
) -> dict:
    """Pre-compile regex patterns for all phrases in the phrase map."""
    cache = {}
    regex_flags = re.IGNORECASE if case_insensitive else 0
    for _path, phrase, _replace, _tinyids in phrase_map:
        if phrase in cache:
            continue
        if phrase.startswith("REGEX:"):
            raw = phrase[6:]
            cache[phrase] = re.compile(raw, regex_flags)
        elif word_boundary or case_insensitive:
            escaped = re.escape(phrase)
            if word_boundary:
                escaped = r"\b" + escaped + r"\b"
            cache[phrase] = re.compile(escaped, regex_flags)
    return cache


# ── TinyId-indexed pattern lookup ─────────────────────────────────────────

def build_tinyid_index(
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]]
) -> Tuple[Dict[str, List[Tuple[str, str, str, Optional[Set[str]]]]], List[Tuple[str, str, str, Optional[Set[str]]]]]:
    """Invert phrase_map to {tinyId: [applicable_entries]}.

    Universal patterns (no tinyId restriction) stored separately.

    Returns:
        (index_dict, universal_list)
    """
    index: Dict[str, list] = defaultdict(list)
    universal: list = []
    for entry in phrase_map:
        _path, _phrase, _replace, tinyids = entry
        if tinyids is None:
            universal.append(entry)
        else:
            for tid in tinyids:
                index[tid].append(entry)
    return dict(index), universal


# ── Core per-field replacement ────────────────────────────────────────────

def _replace_in_text(
    text: str,
    phrase: str,
    replace_with: str,
    compiled_cache: Optional[dict],
) -> str:
    """Replace phrase in text string, returning modified text."""
    if not text or not isinstance(text, str):
        return text

    compiled = compiled_cache.get(phrase) if compiled_cache else None
    if compiled:
        return compiled.sub(replace_with, text)

    if phrase.startswith("REGEX:"):
        raw = phrase[6:]
        return re.sub(raw, replace_with, text)

    # Plain substring
    if phrase in text:
        return text.replace(phrase, replace_with)
    return text


def _apply_phrase_map_to_dict(
    model_data: dict,
    phrase_map: List[Tuple[str, str, str, Optional[Set[str]]]],
    compiled_cache: Optional[dict],
    tinyid_index: Optional[Tuple[dict, list]] = None,
) -> dict:
    """Apply a phrase_map to a single CDE dict, modifying in-place.

    If tinyid_index is provided, only applies patterns relevant to this CDE's
    tinyId (plus universal patterns). Otherwise falls back to per-entry tinyId
    checking.
    """
    tiny_id = model_data.get("tinyId")

    if tinyid_index is not None:
        idx, universal = tinyid_index
        applicable = universal + idx.get(tiny_id, [])
    else:
        applicable = [
            entry for entry in phrase_map
            if entry[3] is None or tiny_id in entry[3]
        ]

    for path, phrase, replace_with, _tinyids in applicable:
        _traverse_and_replace(model_data, path.split("."), phrase, replace_with, compiled_cache)

    return model_data


def _traverse_and_replace(
    obj: Any,
    parts: List[str],
    phrase: str,
    replace_with: str,
    compiled_cache: Optional[dict],
):
    """Recursive field traversal and replacement (mirrors phrase_stripper logic)."""
    if not parts:
        return

    key = parts[0]
    remaining = parts[1:]

    if key == "*":
        # Wildcard: iterate list or dict values
        if isinstance(obj, list):
            for item in obj:
                _traverse_and_replace(item, remaining, phrase, replace_with, compiled_cache)
        elif isinstance(obj, dict):
            for v in obj.values():
                _traverse_and_replace(v, remaining, phrase, replace_with, compiled_cache)
    elif key.startswith("[") and key.endswith("]"):
        # Indexed access: [0], [1], etc.
        idx = int(key[1:-1])
        if isinstance(obj, list) and 0 <= idx < len(obj):
            if remaining:
                _traverse_and_replace(obj[idx], remaining, phrase, replace_with, compiled_cache)
            else:
                if isinstance(obj[idx], str):
                    obj[idx] = _replace_in_text(obj[idx], phrase, replace_with, compiled_cache)
    elif isinstance(obj, dict) and key in obj:
        if remaining:
            _traverse_and_replace(obj[key], remaining, phrase, replace_with, compiled_cache)
        else:
            if isinstance(obj[key], str):
                obj[key] = _replace_in_text(obj[key], phrase, replace_with, compiled_cache)
    elif isinstance(obj, dict):
        # Try numeric key for list-in-dict patterns (e.g. "0" -> obj[0])
        try:
            idx = int(key)
            if isinstance(obj, list) and 0 <= idx < len(obj):
                if remaining:
                    _traverse_and_replace(obj[idx], remaining, phrase, replace_with, compiled_cache)
                else:
                    if isinstance(obj[idx], str):
                        obj[idx] = _replace_in_text(obj[idx], phrase, replace_with, compiled_cache)
        except (ValueError, TypeError):
            pass


# ── Single-CDE N-way strip ────────────────────────────────────────────────

def _strip_single_cde_nway(
    original_data: dict,
    stages: Dict[str, StripStage],
    stage_indexes: Dict[str, Tuple[dict, list]],
    variants: Set[str],
) -> Dict[str, dict]:
    """Compute all requested variants for a single CDE.

    Uses the dependency graph to avoid redundant work:
    - inst_full result is shared between MTSFPF, MTSFPT, MTSTPT
    - inst_sub result is shared between MFSTPF, MFSTPT
    - temporal/phrase applied on top of instrument-stripped results

    Returns:
        {variant_code: processed_dict}
    """
    results = {}

    # Determine which intermediate results we need
    need_inst_full = any(
        "inst_full" in VARIANT_STAGES[v] for v in variants
    )
    need_inst_sub = any(
        "inst_sub" in VARIANT_STAGES[v] for v in variants
    )
    need_inst_full_then_sub = "MTSTPT" in variants

    # ── Stage 1: Instrument stripping ──

    inst_full_data = None
    if need_inst_full and "inst_full" in stages:
        inst_full_data = copy.deepcopy(original_data)
        stage = stages["inst_full"]
        _apply_phrase_map_to_dict(
            inst_full_data, stage.phrase_map, stage.compiled_cache,
            stage_indexes.get("inst_full"),
        )

    inst_sub_data = None
    if need_inst_sub and "inst_sub" in stages:
        inst_sub_data = copy.deepcopy(original_data)
        stage = stages["inst_sub"]
        _apply_phrase_map_to_dict(
            inst_sub_data, stage.phrase_map, stage.compiled_cache,
            stage_indexes.get("inst_sub"),
        )

    # inst_full + inst_sub (for MTSTPT)
    inst_both_data = None
    if need_inst_full_then_sub and inst_full_data is not None and "inst_sub" in stages:
        inst_both_data = copy.deepcopy(inst_full_data)
        stage = stages["inst_sub"]
        _apply_phrase_map_to_dict(
            inst_both_data, stage.phrase_map, stage.compiled_cache,
            stage_indexes.get("inst_sub"),
        )

    # ── Collect instrument-only outputs ──

    if "MTSFPF" in variants and inst_full_data is not None:
        results["MTSFPF"] = copy.deepcopy(inst_full_data)

    if "MFSTPF" in variants and inst_sub_data is not None:
        results["MFSTPF"] = copy.deepcopy(inst_sub_data)

    # ── Stage 2+3: Temporal then phrase stripping ──

    # Helper to apply temporal + phrase stages
    def _apply_temporal_phrase(data: dict) -> dict:
        if "temporal" in stages:
            stage = stages["temporal"]
            _apply_phrase_map_to_dict(
                data, stage.phrase_map, stage.compiled_cache,
                stage_indexes.get("temporal"),
            )
        if "phrase" in stages:
            stage = stages["phrase"]
            _apply_phrase_map_to_dict(
                data, stage.phrase_map, stage.compiled_cache,
                stage_indexes.get("phrase"),
            )
        return data

    # MFSFPT: temporal + phrase on original
    if "MFSFPT" in variants:
        data = copy.deepcopy(original_data)
        results["MFSFPT"] = _apply_temporal_phrase(data)

    # MTSFPT: temporal + phrase on inst_full
    if "MTSFPT" in variants and inst_full_data is not None:
        data = copy.deepcopy(inst_full_data)
        results["MTSFPT"] = _apply_temporal_phrase(data)

    # MFSTPT: temporal + phrase on inst_sub
    if "MFSTPT" in variants and inst_sub_data is not None:
        data = copy.deepcopy(inst_sub_data)
        results["MFSTPT"] = _apply_temporal_phrase(data)

    # MTSTPT: temporal + phrase on inst_full+sub
    if "MTSTPT" in variants and inst_both_data is not None:
        data = copy.deepcopy(inst_both_data)
        results["MTSTPT"] = _apply_temporal_phrase(data)

    return results


# ── Module-level globals for parallel workers ─────────────────────────────

_stages_global: Optional[Dict[str, StripStage]] = None
_stage_indexes_global: Optional[Dict[str, Tuple[dict, list]]] = None
_variants_global: Optional[Set[str]] = None


def _worker_init(stages_data, variants):
    """Initialize worker process with pre-compiled stages."""
    global _stages_global, _stage_indexes_global, _variants_global
    _variants_global = variants

    # Reconstruct StripStage objects and compile patterns
    _stages_global = {}
    _stage_indexes_global = {}
    for name, (phrase_map, case_insensitive, word_boundary) in stages_data.items():
        stage = StripStage(
            name=name,
            phrase_map=phrase_map,
            case_insensitive=case_insensitive,
            word_boundary=word_boundary,
        )
        stage.compile()
        _stages_global[name] = stage
        _stage_indexes_global[name] = build_tinyid_index(phrase_map)


def _worker_process_chunk(args):
    """Process a chunk of CDE dicts, returning per-variant results."""
    chunk_idx, chunk = args
    per_variant: Dict[str, list] = defaultdict(list)

    for data in chunk:
        variant_results = _strip_single_cde_nway(
            data, _stages_global, _stage_indexes_global, _variants_global
        )
        for code, processed in variant_results.items():
            per_variant[code].append(processed)

    return chunk_idx, dict(per_variant)


# ── Main entry point ──────────────────────────────────────────────────────

def strip_branching(
    model_data_list: List[dict],
    stages: Dict[str, StripStage],
    variants: Set[str],
    n_workers: int = 0,
    clean_remnants: bool = False,
    field_paths: Optional[List[str]] = None,
) -> Dict[str, List[dict]]:
    """N-way branching strip: produce all requested variants in one pass.

    Args:
        model_data_list: List of CDE dicts (already converted from Pydantic models).
        stages: Dict of stage_name -> StripStage (pre-configured with phrase maps).
            Expected keys: "inst_full", "inst_sub", "temporal", "phrase".
        variants: Set of variant codes to produce (e.g. {"MTSFPF", "MFSFPT"}).
        n_workers: Parallel workers (0=auto, 1=sequential).
        clean_remnants: If True, run post-strip remnant cleanup on all outputs.
        field_paths: Field paths for clean_remnants (default: definitions + designations).

    Returns:
        Dict of {variant_code: [processed_cde_dict, ...]} maintaining input order.
    """
    if not model_data_list:
        return {v: [] for v in variants}

    # Validate variant codes
    invalid = variants - set(ALL_VARIANT_CODES)
    if invalid:
        raise ValueError(f"Invalid variant codes: {invalid}. Valid: {ALL_VARIANT_CODES}")

    # Compile patterns for each stage
    for stage in stages.values():
        if stage.compiled_cache is None:
            stage.compile()

    # Build tinyId indexes for each stage
    stage_indexes = {
        name: build_tinyid_index(stage.phrase_map)
        for name, stage in stages.items()
    }

    t0 = time.time()
    n_items = len(model_data_list)

    if n_workers == 1 or n_items < 100:
        # Sequential processing
        per_variant: Dict[str, list] = {v: [] for v in variants}

        for i, data in enumerate(model_data_list, 1):
            if i % 5000 == 0:
                logger.info(f"  Processing CDE {i}/{n_items}...")
            variant_results = _strip_single_cde_nway(
                data, stages, stage_indexes, variants
            )
            for code in variants:
                per_variant[code].append(variant_results.get(code, copy.deepcopy(data)))

    else:
        # Parallel processing
        n_workers = get_optimal_workers(n_workers)
        n_workers = min(n_workers, n_items)

        chunk_size = (n_items + n_workers - 1) // n_workers
        chunks = []
        for i in range(0, n_items, chunk_size):
            chunks.append((len(chunks), model_data_list[i:i + chunk_size]))

        logger.info(
            f"Parallel branching strip: {n_items} CDEs across {n_workers} workers "
            f"({len(chunks)} chunks, {len(variants)} variants)"
        )

        # Serialize stage data for workers (avoid pickling compiled regex)
        stages_data = {
            name: (stage.phrase_map, stage.case_insensitive, stage.word_boundary)
            for name, stage in stages.items()
        }

        per_variant: Dict[str, list] = {v: [] for v in variants}
        chunk_results = {}

        with ProcessPoolExecutor(
            max_workers=n_workers,
            initializer=_worker_init,
            initargs=(stages_data, variants),
        ) as executor:
            futures = {
                executor.submit(_worker_process_chunk, chunk): chunk[0]
                for chunk in chunks
            }
            for future in as_completed(futures):
                chunk_idx, chunk_variant_data = future.result()
                chunk_results[chunk_idx] = chunk_variant_data

        # Reassemble in original order
        for chunk_idx in range(len(chunks)):
            chunk_data = chunk_results[chunk_idx]
            original_chunk = chunks[chunk_idx][1]
            for code in variants:
                if code in chunk_data:
                    per_variant[code].extend(chunk_data[code])
                else:
                    # Variant not produced for this chunk — use original data
                    per_variant[code].extend(copy.deepcopy(original_chunk))

    elapsed = time.time() - t0
    logger.info(
        f"Branching strip complete: {n_items} CDEs × {len(variants)} variants "
        f"in {elapsed:.1f}s"
    )

    # Optional post-strip cleanup
    if clean_remnants:
        from logic.remnant_detector import clean_records
        if field_paths is None:
            field_paths = ["definitions.*.definition", "designations.*.designation"]
        for code in variants:
            modified = clean_records(per_variant[code], field_paths)
            if modified:
                logger.info(f"  {code}: cleaned {modified} remnant fields")

    return per_variant
