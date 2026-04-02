#
# File: actions/strip_branching/run.py
#
"""
Orchestration for N-way branching strip action.

Loads CDE JSON once, configures strip stages from pattern TSVs, and invokes
the branching_stripper engine to produce all requested variants simultaneously.

Verbatim strip patterns from config/verbatim_strip_patterns.yaml are
automatically merged into the inst_full stage as universal (no tinyId
restriction) patterns.  Disable with --no-verbatim-patterns.
"""

import json
import logging
import os
import time
from argparse import Namespace

from utils.constants import MODEL_REGISTRY
from utils.file_utils import exit_if_missing, graceful_interrupt

logger = logging.getLogger(__name__)


def _load_patterns_as_phrase_map(
    spec: str,
    field_paths: list,
    sort_order: str = "length",
    expand_anchors: bool = False,
):
    """Load a patterns TSV and convert to phrase_map format.

    Args:
        spec: Pattern file spec (path or path,column).
        field_paths: Field paths for phrase_map entries.
        sort_order: Pattern ordering strategy.
        expand_anchors: If True, expand with anchor prefixes/suffixes.

    Returns:
        List of (path, phrase, replace_with, tinyIds) tuples.
    """
    from actions.strip_phrases.run import (
        load_discovered_patterns,
        expand_patterns_with_anchors,
        patterns_to_phrase_map,
    )

    patterns = load_discovered_patterns(spec)
    logger.info(f"  Loaded {len(patterns)} patterns from {spec.split(',')[0]}")

    if expand_anchors:
        patterns = expand_patterns_with_anchors(patterns)
        logger.info(f"  After anchor expansion: {len(patterns)} patterns")

    phrase_map, _source_map = patterns_to_phrase_map(
        patterns, field_paths, sort_order=sort_order
    )
    return phrase_map


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for strip_branching action."""
    from logic.branching_stripper import StripStage, strip_branching, ALL_VARIANT_CODES

    t0 = time.time()

    # Parse variant codes
    requested_variants = set(
        code.strip() for code in args.variants.split(",") if code.strip()
    )
    invalid = requested_variants - set(ALL_VARIANT_CODES)
    if invalid:
        logger.error(f"Invalid variant codes: {invalid}")
        logger.error(f"Valid codes: {ALL_VARIANT_CODES}")
        raise SystemExit(1)

    logger.info(f"Requested variants: {sorted(requested_variants)}")

    # Load and parse CDE JSON
    model_class = MODEL_REGISTRY[args.model]
    input_path = exit_if_missing(args.input, "Input file")

    logger.info(f"Loading CDE data from {input_path}...")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    from pydantic import ValidationError
    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            logger.error(f"Validation error: {error}")
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} CDE records")

    # Convert to dicts for processing
    model_data_list = [
        model.model_dump(mode="python", exclude_none=False)
        for model in parsed
    ]

    # Determine which stages we need based on requested variants
    from logic.branching_stripper import VARIANT_STAGES
    needed_stages = set()
    for code in requested_variants:
        needed_stages.update(VARIANT_STAGES[code])

    field_paths = args.fields
    sort_order = args.sort_order

    # Build StripStage configs
    stages = {}

    # Load verbatim strip patterns from config (merged into instrument stages)
    verbatim_phrase_map = []
    if getattr(args, 'verbatim_patterns', True):
        from utils.config_loader import load_verbatim_strip_patterns
        verbatim = load_verbatim_strip_patterns()
        if verbatim:
            n_scoped = 0
            for pattern_text, replace_with, tinyids in verbatim:
                for fp in field_paths:
                    verbatim_phrase_map.append((fp, pattern_text, replace_with, tinyids))
                if tinyids is not None:
                    n_scoped += 1
            scoped_msg = f" ({n_scoped} scoped)" if n_scoped else ""
            logger.info(f"Loaded {len(verbatim)} verbatim patterns{scoped_msg} from config "
                        f"({len(verbatim_phrase_map)} phrase_map entries)")

    if "inst_full" in needed_stages:
        if not args.inst_full_patterns:
            logger.error("--inst-full-patterns required for variants: "
                         + ", ".join(v for v in requested_variants
                                     if "inst_full" in VARIANT_STAGES[v]))
            raise SystemExit(1)
        phrase_map = _load_patterns_as_phrase_map(
            args.inst_full_patterns, field_paths, sort_order,
            expand_anchors=True,  # instrument patterns use anchor expansion
        )
        if verbatim_phrase_map:
            phrase_map.extend(verbatim_phrase_map)
            logger.info(f"  Merged {len(verbatim_phrase_map)} verbatim entries "
                        f"into inst_full stage")
        stages["inst_full"] = StripStage(
            name="inst_full", phrase_map=phrase_map,
        )

    if "inst_sub" in needed_stages:
        if not args.inst_sub_patterns:
            logger.error("--inst-sub-patterns required for variants: "
                         + ", ".join(v for v in requested_variants
                                     if "inst_sub" in VARIANT_STAGES[v]))
            raise SystemExit(1)
        phrase_map = _load_patterns_as_phrase_map(
            args.inst_sub_patterns, field_paths, sort_order,
            expand_anchors=True,
        )
        stages["inst_sub"] = StripStage(
            name="inst_sub", phrase_map=phrase_map,
        )

    if "temporal" in needed_stages:
        if not args.temporal_patterns:
            logger.error("--temporal-patterns required for variants: "
                         + ", ".join(v for v in requested_variants
                                     if "temporal" in VARIANT_STAGES[v]))
            raise SystemExit(1)
        phrase_map = _load_patterns_as_phrase_map(
            args.temporal_patterns, field_paths, sort_order,
            expand_anchors=False,  # temporal patterns: no anchor expansion
        )
        stages["temporal"] = StripStage(
            name="temporal", phrase_map=phrase_map,
            case_insensitive=True,  # temporal: --ignore-case
            word_boundary=True,      # temporal: --word-boundary
        )

    if "phrase" in needed_stages:
        if not args.phrase_patterns:
            logger.error("--phrase-patterns required for variants: "
                         + ", ".join(v for v in requested_variants
                                     if "phrase" in VARIANT_STAGES[v]))
            raise SystemExit(1)
        phrase_map = _load_patterns_as_phrase_map(
            args.phrase_patterns, field_paths, sort_order,
            expand_anchors=False,  # phrase patterns: no anchor expansion
        )
        stages["phrase"] = StripStage(
            name="phrase", phrase_map=phrase_map,
            case_insensitive=False,  # curated phrases: case-sensitive
            word_boundary=True,       # curated phrases: --word-boundary
        )

    # Log stage summary
    for name, stage in stages.items():
        n_patterns = len(set(p[1] for p in stage.phrase_map))
        logger.info(f"Stage '{name}': {n_patterns} unique patterns, "
                    f"case_insensitive={stage.case_insensitive}, "
                    f"word_boundary={stage.word_boundary}")

    # Run the N-way branching strip
    logger.info("Running N-way branching strip...")
    results = strip_branching(
        model_data_list,
        stages=stages,
        variants=requested_variants,
        n_workers=args.workers,
        clean_remnants=args.clean_remnants,
        field_paths=field_paths,
    )

    # Write outputs
    os.makedirs(args.output_dir, exist_ok=True)

    # Reconstruct Pydantic models for JSON serialization
    for code in sorted(requested_variants):
        variant_data = results[code]
        output_path = os.path.join(args.output_dir, f"stripped_{code}.json")

        # Convert dicts to JSON-serializable format via Pydantic
        json_data = []
        for d in variant_data:
            model = model_class.model_validate(d)
            json_data.append(model.model_dump(mode="json"))

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            f.write(json.dumps(json_data, indent=2))
        logger.info(f"Wrote {code}: {len(json_data)} records -> {output_path}")

    elapsed = time.time() - t0
    logger.info(f"Total time: {elapsed:.1f}s for {len(requested_variants)} variants")
    return 0
