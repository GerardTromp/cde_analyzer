#
# File: actions/abbreviation/run.py
#
"""
Abbreviation — Run module for discovery, expansion, classification, and export.
"""
import json
import os
from argparse import Namespace
from pathlib import Path

from utils.logger import logging
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


@graceful_interrupt
def run_action(args: Namespace):
    from logic.abbreviation_dictionary import AbbreviationDictionary

    if args.discover:
        return _run_discover(args)
    elif args.expand:
        return _run_expand(args, args.expand)
    elif args.classify:
        return _run_classify(args, args.classify)
    elif args.export_strip:
        return _run_export_strip(args, args.export_strip)
    elif args.export_scoped:
        return _run_export_scoped(args, args.export_scoped)
    elif args.stats:
        return _run_stats(args, args.stats)
    elif args.merge:
        return _run_merge(args, args.merge)
    elif getattr(args, "pipeline", False):
        return _run_pipeline(args)

    logger.error("No mode specified")
    return 1


def _load_json(args) -> list:
    """Load CDE JSON from --input."""
    input_path = getattr(args, "input", None)
    if not input_path:
        logger.error("--input is required")
        raise SystemExit(1)
    input_path = str(Path(input_path).resolve())
    logger.info(f"Loading data from {input_path}")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} records")
    return data


def _run_discover(args) -> int:
    """Discover all abbreviation types in the corpus."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    data = _load_json(args)
    output = getattr(args, "output", None)
    if not output:
        logger.error("--output is required for --discover")
        raise SystemExit(1)

    dictionary = AbbreviationDictionary(output)

    # Load English words for filtering
    english_words = None
    try:
        from utils.instrument_extractor import _load_english_words
        english_words = _load_english_words()
    except ImportError:
        pass

    print("\nDiscovering abbreviations...")

    n_paren = dictionary.discover_parenthetical(data)
    print(f"  Parenthetical (ABBREV): {n_paren} new entries")

    n_bracket = dictionary.discover_bracketed(data)
    print(f"  Bracketed [TAG]: {n_bracket} new entries")

    n_caps = dictionary.discover_bare_caps(data, english_words=english_words)
    print(f"  Bare CAPS: {n_caps} new entries")

    n_intercaps = 0
    if not getattr(args, "no_intercaps", False):
        n_intercaps = dictionary.discover_intercaps(data)
        print(f"  InterCaps: {n_intercaps} new entries")

    # Filter by min occurrences
    min_occ = getattr(args, "min_occurrences", 1)
    if min_occ > 1:
        before = len(dictionary.entries)
        dictionary.entries = {
            k: v for k, v in dictionary.entries.items()
            if v.n_tinyIds >= min_occ
        }
        print(f"  Filtered: {before} -> {len(dictionary.entries)} "
              f"(min_occurrences={min_occ})")

    dictionary.save(output)
    total = len(dictionary.entries)
    print(f"\nTotal: {total} entries -> {output}")

    # Summary
    summary = dictionary.summary()
    for cat, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    return 0


def _run_expand(args, dict_path: str) -> int:
    """Expand abbreviations using CDE definitions and instrument catalog."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    data = _load_json(args)
    output = getattr(args, "output", None) or dict_path

    dictionary = AbbreviationDictionary(dict_path)
    if not dictionary.load():
        logger.error(f"Dictionary not found: {dict_path}")
        raise SystemExit(1)

    print(f"\nExpanding {len(dictionary.entries)} entries...")

    n_context = dictionary.expand_from_context(data)
    print(f"  From CDE definitions: {n_context} expanded")

    # Try instrument catalog if available
    n_catalog = 0
    # (Catalog integration deferred — requires running instrument_miner first)

    with_expansion = sum(1 for e in dictionary.entries.values() if e.expansion)
    without = len(dictionary.entries) - with_expansion
    print(f"\n  With expansion: {with_expansion}")
    print(f"  Without expansion: {without}")

    dictionary.save(output)
    print(f"\nSaved: {output}")
    return 0


def _run_classify(args, dict_path: str) -> int:
    """Classify abbreviations using heuristic rules."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    output = getattr(args, "output", None) or dict_path

    dictionary = AbbreviationDictionary(dict_path)
    if not dictionary.load():
        logger.error(f"Dictionary not found: {dict_path}")
        raise SystemExit(1)

    print(f"\nClassifying {len(dictionary.entries)} entries...")

    # Heuristic classification
    n_heuristic = dictionary.classify_by_heuristic()
    print(f"  By heuristic (expansion words): {n_heuristic}")

    # Family detector classification
    n_family = 0
    try:
        from utils.instrument_family_patterns import FAMILY_PATTERNS
        n_family = dictionary.classify_by_family_detector(FAMILY_PATTERNS)
        print(f"  By family detector: {n_family}")
    except ImportError:
        pass

    # Summary
    summary = dictionary.summary()
    print(f"\nClassification summary:")
    for cat, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # Export needs_review
    threshold = getattr(args, "confidence_threshold", 0.8)
    needs_review = [e for e in dictionary.entries.values()
                    if e.confidence < threshold or e.category == "unknown"]
    if needs_review:
        review_path = str(Path(output).with_suffix("")) + "_needs_review.tsv"
        n_review = dictionary.export_needs_review(review_path, threshold)
        print(f"\n  Needs review: {n_review} entries -> {review_path}")

    dictionary.save(output)
    print(f"\nSaved: {output}")
    return 0


def _run_export_strip(args, dict_path: str) -> int:
    """Export verbatim strip patterns YAML."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    output = getattr(args, "output", None)
    if not output:
        logger.error("--output is required for --export-strip")
        raise SystemExit(1)

    dictionary = AbbreviationDictionary(dict_path)
    if not dictionary.load():
        logger.error(f"Dictionary not found: {dict_path}")
        raise SystemExit(1)

    categories = [c.strip() for c in args.categories.split(",")]
    n = dictionary.export_strip_patterns(output, categories)
    print(f"\nExported {n} strip patterns -> {output}")
    return 0


def _run_export_scoped(args, dict_path: str) -> int:
    """Export tinyId-scoped patterns TSV."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    output = getattr(args, "output", None)
    if not output:
        logger.error("--output is required for --export-scoped")
        raise SystemExit(1)

    dictionary = AbbreviationDictionary(dict_path)
    if not dictionary.load():
        logger.error(f"Dictionary not found: {dict_path}")
        raise SystemExit(1)

    categories = [c.strip() for c in args.categories.split(",")]
    n = dictionary.export_scoped_patterns(output, categories)
    print(f"\nExported {n} scoped patterns -> {output}")
    return 0


def _run_stats(args, dict_path: str) -> int:
    """Print dictionary statistics."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    dictionary = AbbreviationDictionary(dict_path)
    if not dictionary.load():
        logger.error(f"Dictionary not found: {dict_path}")
        raise SystemExit(1)

    total = len(dictionary.entries)
    summary = dictionary.summary()
    with_expansion = sum(1 for e in dictionary.entries.values() if e.expansion)
    total_tinyids = sum(e.n_tinyIds for e in dictionary.entries.values())

    print(f"\nAbbreviation Dictionary: {dict_path}")
    print(f"  Total entries: {total}")
    print(f"  With expansion: {with_expansion} ({with_expansion/total*100:.0f}%)"
          if total else "")
    print(f"  Total tinyId references: {total_tinyids}")
    print(f"\n  By category:")
    for cat, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")

    print(f"\n  By source:")
    sources: dict = {}
    for e in dictionary.entries.values():
        sources[e.source] = sources.get(e.source, 0) + 1
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"    {src}: {count}")

    print(f"\n  By confidence:")
    high = sum(1 for e in dictionary.entries.values() if e.confidence >= 0.8)
    med = sum(1 for e in dictionary.entries.values() if 0.5 <= e.confidence < 0.8)
    low = sum(1 for e in dictionary.entries.values() if e.confidence < 0.5)
    print(f"    High (>=0.8): {high}")
    print(f"    Medium (0.5-0.8): {med}")
    print(f"    Low (<0.5): {low}")

    return 0


def _run_pipeline(args) -> int:
    """Run full abbreviation pipeline: discover → expand → classify → seed → export."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    data = _load_json(args)
    output_dir = getattr(args, "output", None)
    if not output_dir:
        logger.error("--output (directory) is required for --pipeline")
        raise SystemExit(1)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    dict_path = out / "abbreviation_dictionary.tsv"
    verbatim_path = out / "abbreviation_verbatim.yaml"
    scoped_path = out / "abbreviation_scoped.tsv"
    review_path = out / "abbreviation_needs_review.tsv"

    # Step 1: Discover
    print("\n=== Step 1: Discover abbreviations ===")
    dictionary = AbbreviationDictionary(str(dict_path))

    english_words = None
    try:
        from utils.instrument_extractor import _load_english_words
        english_words = _load_english_words()
    except ImportError:
        pass

    n_paren = dictionary.discover_parenthetical(data)
    print(f"  Parenthetical: {n_paren}")
    n_bracket = dictionary.discover_bracketed(data)
    print(f"  Bracketed: {n_bracket}")
    n_caps = dictionary.discover_bare_caps(data, english_words=english_words)
    print(f"  Bare CAPS: {n_caps}")
    if not getattr(args, "no_intercaps", False):
        n_intercaps = dictionary.discover_intercaps(data)
        print(f"  InterCaps: {n_intercaps}")

    # Step 2: Expand
    print("\n=== Step 2: Expand from context ===")
    n_context = dictionary.expand_from_context(data)
    print(f"  Expanded: {n_context}")

    # Step 3: Seed from reference dictionary
    print("\n=== Step 3: Seed from reference dictionary ===")
    try:
        from utils.config_loader import load_abbreviation_dictionary
        ref_dict = load_abbreviation_dictionary()
        if ref_dict:
            seeded = 0
            for abbrev, ref_entry in ref_dict.entries.items():
                if abbrev in dictionary.entries:
                    entry = dictionary.entries[abbrev]
                    # Apply reference classification + decision if entry is unknown
                    if entry.category == "unknown" and ref_entry.category != "unknown":
                        entry.category = ref_entry.category
                        entry.confidence = max(entry.confidence, ref_entry.confidence)
                        entry.decision = ref_entry.decision
                        if ref_entry.expansion and not entry.expansion:
                            entry.expansion = ref_entry.expansion
                        seeded += 1
                    elif not entry.decision and ref_entry.decision:
                        entry.decision = ref_entry.decision
                        seeded += 1
            print(f"  Seeded from reference: {seeded}")
        else:
            print("  No reference dictionary found")
    except Exception as e:
        print(f"  Reference seeding skipped: {e}")

    # Step 4: Classify
    print("\n=== Step 4: Classify by heuristic + family detector ===")
    n_heuristic = dictionary.classify_by_heuristic()
    print(f"  By heuristic: {n_heuristic}")

    n_family = 0
    try:
        from utils.instrument_family_patterns import FAMILY_PATTERNS
        n_family = dictionary.classify_by_family_detector(FAMILY_PATTERNS)
        print(f"  By family detector: {n_family}")
    except ImportError:
        pass

    # Summary
    summary = dictionary.summary()
    print(f"\n  Classification:")
    for cat, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")

    decisions = {}
    for e in dictionary.entries.values():
        d = e.decision or "(none)"
        decisions[d] = decisions.get(d, 0) + 1
    print(f"  Decisions:")
    for d, n in sorted(decisions.items(), key=lambda x: -x[1]):
        print(f"    {d}: {n}")

    # Step 5: Save + Export
    print("\n=== Step 5: Save + Export ===")
    dictionary.save()
    print(f"  Dictionary: {len(dictionary.entries)} entries → {dict_path}")

    categories = [c.strip() for c in args.categories.split(",")]
    n_verb = dictionary.export_strip_patterns(str(verbatim_path), categories)
    print(f"  Verbatim patterns: {n_verb} → {verbatim_path}")

    n_scoped = dictionary.export_scoped_patterns(str(scoped_path), categories)
    print(f"  Scoped patterns: {n_scoped} → {scoped_path}")

    n_review = dictionary.export_needs_review(str(review_path))
    print(f"  Needs review: {n_review} → {review_path}")

    return 0


def _run_merge(args, paths: list) -> int:
    """Merge two dictionaries."""
    from logic.abbreviation_dictionary import AbbreviationDictionary

    output = getattr(args, "output", None)
    if not output:
        logger.error("--output is required for --merge")
        raise SystemExit(1)

    base = AbbreviationDictionary(paths[0])
    update = AbbreviationDictionary(paths[1])

    if not base.load():
        logger.error(f"Base dictionary not found: {paths[0]}")
        raise SystemExit(1)
    if not update.load():
        logger.error(f"Update dictionary not found: {paths[1]}")
        raise SystemExit(1)

    counts = base.merge(update)
    base.save(output)

    print(f"\nMerged: {paths[0]} + {paths[1]} -> {output}")
    print(f"  Added: {counts['added']}")
    print(f"  Updated: {counts['updated']}")
    print(f"  Unchanged: {counts['unchanged']}")
    print(f"  Total: {len(base.entries)}")
    return 0
