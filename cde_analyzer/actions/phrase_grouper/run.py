"""Orchestration layer for phrase_grouper action"""

import csv
import logging
from argparse import Namespace
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


@dataclass
class PhraseRecord:
    """A phrase loaded from verbatim_phrases.tsv"""
    phrase_id: str
    text: str
    tokens: List[str]
    tinyids: Set[str]


@graceful_interrupt
def run_action(args: Namespace):
    """
    Main entry point for phrase_grouper action.
    Loads phrases, builds family trees, outputs groupings.

    Args:
        args: Parsed command-line arguments
    """
    from logic.phrase_grouper import (
        build_prefix_tree,
        build_suffix_tree,
        build_infix_index,
        extract_families,
        assign_phrases_to_families,
        GrouperConfig,
    )

    # 1. Load phrases from TSV
    logger.info(f"Loading phrases from {args.input}")
    phrases = load_phrases_tsv(
        args.input,
        text_col=args.text_column,
        id_col=args.id_column,
        tinyid_col=args.tinyid_column,
        lowercase=args.lowercase,
    )
    logger.info(f"Loaded {len(phrases)} phrases")

    if len(phrases) < args.min_family_size:
        logger.warning(f"Too few phrases ({len(phrases)}) to form families "
                       f"(min_family_size={args.min_family_size})")
        return 0

    # 2. Build configuration
    min_content_words = getattr(args, 'min_content_words', 1)
    config = GrouperConfig(
        k_min=args.k_min,
        k_max=args.k_max,
        min_family_size=args.min_family_size,
        min_pattern_freq=args.min_pattern_freq,
        min_content_words=min_content_words,
        assignment_strategy=args.assignment,
    )

    logger.info(f"Configuration: k={args.k_min}-{args.k_max}, "
                f"min_family_size={args.min_family_size}, "
                f"min_content_words={min_content_words}, "
                f"assignment={args.assignment}")

    # 3. Build trees (optionally in parallel)
    trees_to_build = args.trees
    logger.info(f"Building trees: {', '.join(trees_to_build)}")

    results = {}

    if args.parallel and len(trees_to_build) > 1:
        # Parallel execution
        from concurrent.futures import ProcessPoolExecutor, as_completed

        with ProcessPoolExecutor(max_workers=len(trees_to_build)) as executor:
            futures = {}
            if "prefix" in trees_to_build:
                futures[executor.submit(build_prefix_tree, phrases, config)] = "prefix"
            if "suffix" in trees_to_build:
                futures[executor.submit(build_suffix_tree, phrases, config)] = "suffix"
            if "infix" in trees_to_build:
                futures[executor.submit(build_infix_index, phrases, config)] = "infix"

            for future in as_completed(futures):
                tree_type = futures[future]
                try:
                    results[tree_type] = future.result()
                    logger.info(f"Completed {tree_type} tree")
                except Exception as e:
                    logger.error(f"Error building {tree_type} tree: {e}")
    else:
        # Sequential execution
        if "prefix" in trees_to_build:
            logger.info("Building prefix tree...")
            results["prefix"] = build_prefix_tree(phrases, config)
        if "suffix" in trees_to_build:
            logger.info("Building suffix tree...")
            results["suffix"] = build_suffix_tree(phrases, config)
        if "infix" in trees_to_build:
            logger.info("Building infix index...")
            results["infix"] = build_infix_index(phrases, config)

    # 4. Extract families from each tree
    all_families = {}
    for tree_type, tree_data in results.items():
        families = extract_families(tree_data, tree_type, config)
        all_families[tree_type] = families
        logger.info(f"{tree_type.capitalize()} tree: {len(families)} families found")

    # 5. Assign phrases to best-fit families
    assignments = assign_phrases_to_families(phrases, all_families, config)

    # 6. Write outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write family summary
    write_families_tsv(all_families, output_dir / "families.tsv")

    # Write phrase assignments
    write_assignments_tsv(assignments, output_dir / "phrase_assignments.tsv")

    # Write detailed family members
    write_family_members_tsv(all_families, phrases, output_dir / "family_members.tsv")

    # Log summary statistics
    total_families = sum(len(f) for f in all_families.values())
    assigned_count = sum(1 for a in assignments.values() if a.get("family_id"))
    logger.info(f"Results: {total_families} families, "
                f"{assigned_count}/{len(phrases)} phrases assigned")
    logger.info(f"Output written to {output_dir}")

    return 0


def load_phrases_tsv(
    path: str,
    text_col: str = "verbatim_text",
    id_col: str = "phrase_id",
    tinyid_col: str = "tinyids",
    lowercase: bool = False,
) -> List[PhraseRecord]:
    """
    Load phrases from a TSV file (typically verbatim_phrases.tsv).

    Args:
        path: Path to TSV file
        text_col: Column containing phrase text
        id_col: Column containing phrase ID
        tinyid_col: Column containing pipe-separated tinyIds
        lowercase: Normalize text to lowercase

    Returns:
        List of PhraseRecord objects
    """
    phrases = []

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')

        # Validate columns exist
        if text_col not in reader.fieldnames:
            raise ValueError(f"Column '{text_col}' not found. "
                             f"Available: {reader.fieldnames}")

        for row in reader:
            text = row.get(text_col, "").strip()
            if not text:
                continue

            if lowercase:
                text = text.lower()

            # Tokenize on whitespace (simple tokenization)
            tokens = text.split()
            if len(tokens) < 2:
                continue  # Skip single-token phrases

            phrase_id = row.get(id_col, f"phrase_{len(phrases)}")
            tinyids_str = row.get(tinyid_col, "")
            tinyids = set(tinyids_str.split("|")) if tinyids_str else set()

            phrases.append(PhraseRecord(
                phrase_id=phrase_id,
                text=text,
                tokens=tokens,
                tinyids=tinyids,
            ))

    return phrases


def write_families_tsv(
    all_families: Dict[str, List[dict]],
    path: Path
) -> int:
    """
    Write families.tsv summary with one row per family.

    Columns: family_id, family_type, pattern, member_count, total_tinyids, example_phrases
    """
    count = 0
    with path.open('w', encoding='utf-8') as f:
        f.write("family_id\tfamily_type\tpattern\tmember_count\ttotal_tinyids\texample_phrases\n")

        for family_type, families in all_families.items():
            for family in families:
                examples = " | ".join(family.get("examples", [])[:3])
                examples = examples.replace('\t', ' ').replace('\n', ' ')

                f.write(f"{family['family_id']}\t{family_type}\t"
                        f"{family['pattern']}\t{family['member_count']}\t"
                        f"{family['total_tinyids']}\t{examples}\n")
                count += 1

    logger.info(f"Wrote {count} families to {path.name}")
    return count


def write_assignments_tsv(
    assignments: Dict[str, dict],
    path: Path
) -> int:
    """
    Write phrase_assignments.tsv mapping phrases to their best-fit family.

    Columns: phrase_id, phrase_text, family_id, family_type, pattern, confidence
    """
    count = 0
    with path.open('w', encoding='utf-8') as f:
        f.write("phrase_id\tphrase_text\tfamily_id\tfamily_type\tpattern\tconfidence\n")

        for phrase_id, assignment in assignments.items():
            text = assignment.get("text", "").replace('\t', ' ').replace('\n', ' ')
            family_id = assignment.get("family_id", "")
            family_type = assignment.get("family_type", "")
            pattern = assignment.get("pattern", "").replace('\t', ' ')
            confidence = assignment.get("confidence", 0.0)

            f.write(f"{phrase_id}\t{text}\t{family_id}\t{family_type}\t"
                    f"{pattern}\t{confidence:.3f}\n")
            count += 1

    logger.info(f"Wrote {count} assignments to {path.name}")
    return count


def write_family_members_tsv(
    all_families: Dict[str, List[dict]],
    phrases: List[PhraseRecord],
    path: Path
) -> int:
    """
    Write family_members.tsv with detailed member listing.

    Columns: family_id, family_type, pattern, phrase_id, phrase_text, tinyids
    """
    # Build phrase lookup
    phrase_lookup = {p.phrase_id: p for p in phrases}

    count = 0
    with path.open('w', encoding='utf-8') as f:
        f.write("family_id\tfamily_type\tpattern\tphrase_id\tphrase_text\ttinyids\n")

        for family_type, families in all_families.items():
            for family in families:
                pattern = family['pattern'].replace('\t', ' ')

                for phrase_id in family.get("member_ids", []):
                    phrase = phrase_lookup.get(phrase_id)
                    if phrase:
                        text = phrase.text.replace('\t', ' ').replace('\n', ' ')
                        tinyids = "|".join(sorted(phrase.tinyids))

                        f.write(f"{family['family_id']}\t{family_type}\t"
                                f"{pattern}\t{phrase_id}\t{text}\t{tinyids}\n")
                        count += 1

    logger.info(f"Wrote {count} family member rows to {path.name}")
    return count
