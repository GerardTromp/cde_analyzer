#
# File: actions/pattern_util/run.py
#
"""
Pattern Util - Run module for TSV pattern manipulation.

Provides merge, coalesce, and supplementary import utilities.
"""
import os
from argparse import Namespace

from utils.logger import logging
from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


def add_patterns_to_supplementary(
    curated_tsv_path: str,
    section_name: str = "added_patterns",
    delete_after: bool = True
) -> int:
    """
    Add patterns from curated TSV to supplementary_patterns.yaml.

    Args:
        curated_tsv_path: Path to curated TSV file with 'pattern', 'name' columns
        section_name: YAML section name for imported patterns
        delete_after: If True, delete the TSV file after successful import

    Returns:
        Number of patterns added
    """
    from utils.config_loader import get_config_dir

    config_path = get_config_dir() / "supplementary_patterns.yaml"
    if not config_path.exists():
        logger.error(f"supplementary_patterns.yaml not found at {config_path}")
        raise SystemExit(1)

    # Load existing YAML
    import yaml
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Parse curated TSV - only include rows where 'include' column is 'yes'
    patterns_to_add = []
    with open(curated_tsv_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = [h.lower() for h in header_line.split('\t')]

        # Find required columns
        try:
            pattern_idx = headers.index('pattern')
            name_idx = headers.index('suggested_name') if 'suggested_name' in headers else headers.index('name')
        except ValueError as e:
            logger.error(f"Required column not found: {e}")
            raise SystemExit(1)

        # Find optional columns
        acronym_idx = headers.index('acronym') if 'acronym' in headers else -1
        include_idx = headers.index('include') if 'include' in headers else -1

        for line in f:
            line = line.strip()
            if not line:
                continue

            fields = line.split('\t')

            # Check include flag if present
            # Strip Excel's auto-added quotes around fields containing commas
            if include_idx >= 0 and include_idx < len(fields):
                include_val = fields[include_idx].strip().strip('"').lower()
                if include_val not in ('yes', 'y', 'true', '1'):
                    continue

            if pattern_idx >= len(fields) or name_idx >= len(fields):
                continue

            pattern = fields[pattern_idx].strip().strip('"')
            name = fields[name_idx].strip().strip('"')

            if not pattern or not name:
                continue

            entry = {'pattern': pattern, 'name': name}

            if acronym_idx >= 0 and acronym_idx < len(fields):
                acronym = fields[acronym_idx].strip().strip('"')
                if acronym:
                    entry['acronym'] = acronym

            patterns_to_add.append(entry)

    if not patterns_to_add:
        logger.warning("No patterns marked for inclusion (set 'include' column to 'yes')")
        return 0

    # Add to config
    if section_name not in config:
        config[section_name] = []

    # Check for duplicates
    existing_patterns = set()
    for section in config.values():
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict) and 'pattern' in item:
                    existing_patterns.add(item['pattern'])

    added_count = 0
    for entry in patterns_to_add:
        if entry['pattern'] not in existing_patterns:
            config[section_name].append(entry)
            existing_patterns.add(entry['pattern'])
            added_count += 1
        else:
            logger.warning(f"Skipping duplicate pattern: {entry['pattern']}")

    # Write updated YAML
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(f"Added {added_count} patterns to {section_name} section")

    # Delete input file if requested
    if delete_after and added_count > 0:
        os.remove(curated_tsv_path)
        logger.info(f"Deleted curated file: {curated_tsv_path}")

    return added_count


@graceful_interrupt
def run_action(args: Namespace):
    """Main entry point for pattern_util action."""

    # Check for add-to-supplementary mode first (standalone)
    add_to_supplementary = getattr(args, 'add_to_supplementary', None)
    if add_to_supplementary:
        section_name = getattr(args, 'supplementary_section', 'added_patterns')
        count = add_patterns_to_supplementary(
            add_to_supplementary,
            section_name=section_name,
            delete_after=True
        )
        print(f"Added {count} patterns to supplementary_patterns.yaml ({section_name} section)")
        if count > 0:
            print("Input file deleted. Re-run phrase_miner with --extract-supplementary to pick up new patterns.")
        return 0

    # Check for merge mode
    merge_patterns = getattr(args, 'merge_patterns', None)
    if merge_patterns:
        if not getattr(args, 'output', None):
            logger.error("--output is required for --merge-patterns")
            raise SystemExit(1)
        from utils.flexible_pattern_matcher import merge_verbatim_tsv

        pattern_column = getattr(args, 'merge_pattern_column', 'pattern')
        tinyids_column = getattr(args, 'merge_tinyids_column', 'tinyIds')

        logger.info(f"Merge mode: combining duplicate patterns in {merge_patterns}")
        stats = merge_verbatim_tsv(
            merge_patterns,
            args.output,
            pattern_column=pattern_column,
            tinyids_column=tinyids_column
        )

        print(f"Input:  {stats['input_rows']} rows")
        print(f"Output: {stats['output_rows']} unique patterns")
        print(f"Merged: {stats['merged_count']} duplicate patterns")
        print(f"Wrote:  {args.output}")
        return 0

    # Check for coalesce mode
    coalesce_variants = getattr(args, 'coalesce_variants', None)
    if coalesce_variants:
        if not getattr(args, 'output', None):
            logger.error("--output is required for --coalesce-variants")
            raise SystemExit(1)
        from utils.flexible_pattern_matcher import coalesce_variants_tsv

        pattern_column = getattr(args, 'merge_pattern_column', 'pattern')
        tinyids_column = getattr(args, 'merge_tinyids_column', 'tinyIds')
        report_path = getattr(args, 'coalesce_report', None)
        min_prefix_tinyids = getattr(args, 'min_prefix_tinyids', 0)

        logger.info(f"Coalesce mode: removing subsumed patterns from {coalesce_variants}")
        if min_prefix_tinyids > 0:
            logger.info(f"Prefix extraction enabled (min_tinyids={min_prefix_tinyids})")

        stats = coalesce_variants_tsv(
            coalesce_variants,
            args.output,
            pattern_column=pattern_column,
            tinyids_column=tinyids_column,
            report_path=report_path,
            min_prefix_tinyids=min_prefix_tinyids
        )

        print(f"\nCoalesce complete:")
        print(f"  Input:    {stats['input_patterns']} patterns")
        print(f"  Output:   {stats['output_patterns']} patterns")
        print(f"  Subsumed: {stats['subsumed_count']} patterns removed")
        if stats.get('prefix_extracted_count', 0) > 0:
            print(f"  Prefixes: {stats['prefix_extracted_count']} patterns -> common stems")
        if report_path:
            print(f"  Report:   {report_path}")
        print(f"  Wrote:    {args.output}")

        # Show a few examples of subsumptions
        if stats['subsumptions']:
            print(f"\nExample subsumptions (showing first 5):")
            for pattern, covers in stats['subsumptions'][:5]:
                cover_sample = covers[0][:40] if covers else "?"
                if len(covers) > 1:
                    cover_sample += f" (+{len(covers)-1} more)"
                print(f"  '{pattern[:50]}' -> '{cover_sample}'")

        return 0

    # No mode specified
    logger.error("No mode specified. Use --merge-patterns, --coalesce-variants, or --add-to-supplementary.")
    print("\nUsage:")
    print("  cde-analyzer pattern_util --merge-patterns FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --coalesce-variants FILE -o OUTPUT")
    print("  cde-analyzer pattern_util --add-to-supplementary FILE")
    raise SystemExit(1)
