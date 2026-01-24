#
# File: actions/llm_classify/run.py
#
# Orchestration for the llm_classify action.
#

import asyncio
import sys
import logging
from argparse import Namespace
from pathlib import Path

logger = logging.getLogger(__name__)


def run_action(args: Namespace):
    """
    Run LLM-based phrase classification.

    Coordinates loading phrase_miner output, querying LLM providers,
    and writing aggregated classification results.
    """
    # Validate input directory
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(
            f"error: Input directory not found: {input_dir}",
            file=sys.stderr,
        )
        sys.exit(2)

    phrases_file = input_dir / "phrases.tsv"
    if not phrases_file.exists():
        print(
            f"error: phrases.tsv not found in {input_dir}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Prepare paths
    output_dir = Path(args.output_dir)
    config_file = Path(args.config_file) if args.config_file else None
    reference_file = Path(args.reference_file) if args.reference_file else None
    original_cdes = Path(args.original_cdes) if args.original_cdes else None

    # Validate reference file if provided
    if reference_file and not reference_file.exists():
        print(
            f"error: Reference file not found: {reference_file}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Import here to enable lazy loading
    from logic.llm_classifier import run_classification

    logger.info(f"Starting LLM classification")
    logger.info(f"  Input directory: {input_dir}")
    logger.info(f"  Output directory: {output_dir}")
    logger.info(f"  Query module: {args.module}")
    logger.info(f"  Providers: {args.providers}")
    logger.info(f"  Aggregation method: {args.aggregation_method}")

    if args.dry_run:
        logger.info("Dry run mode - validating configuration only")
        _run_dry_run(args, input_dir, config_file)
        return

    # Run the async classification pipeline
    try:
        results, stats = asyncio.run(
            run_classification(
                input_dir=input_dir,
                output_dir=output_dir,
                module_name=args.module,
                providers=args.providers,
                config_file=config_file,
                api_keys=args.api_keys,
                aggregation_method=args.aggregation_method,
                batch_size=args.batch_size,
                min_frequency=args.min_frequency,
                context_window=args.context_window,
                reference_file=reference_file,
                original_cdes=original_cdes,
                validate_keys=not args.skip_validation,
            )
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception("Classification failed")
        print(f"error: Classification failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    _print_summary(stats, output_dir, args.module)


def _run_dry_run(args: Namespace, input_dir: Path, config_file: Path):
    """
    Validate configuration without making LLM calls.
    """
    from utils.llm import resolve_config
    from utils.query_modules import get_module
    import csv

    # Check API key resolution
    print("\nChecking API key configuration...")
    try:
        llm_config = resolve_config(
            requested_providers=args.providers,
            config_file_path=config_file,
            cli_api_keys=args.api_keys,
        )
        for provider_config in llm_config.get_providers():
            key_preview = provider_config.api_key[:8] + "..." if provider_config.api_key else "None"
            print(f"  {provider_config.provider}: key={key_preview} (source: {provider_config.source})")
    except Exception as e:
        print(f"  error: {e}")
        sys.exit(2)

    # Check query module
    print(f"\nLoading query module: {args.module}")
    try:
        module = get_module(args.module)
        print(f"  Categories: {module.output_categories}")
        print(f"  Description: {module.description}")
    except Exception as e:
        print(f"  error: {e}")
        sys.exit(2)

    # Count phrases
    print(f"\nCounting phrases in {input_dir}...")
    phrases_file = input_dir / "phrases.tsv"
    phrase_count = 0
    filtered_count = 0

    with open(phrases_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            phrase_count += 1
            freq = int(row.get("frequency", row.get("count", 0)))
            if freq >= args.min_frequency:
                filtered_count += 1

    print(f"  Total phrases: {phrase_count}")
    print(f"  After min_frequency={args.min_frequency} filter: {filtered_count}")

    print("\nDry run complete. Configuration is valid.")


def _print_summary(stats: dict, output_dir: Path, module_name: str):
    """
    Print classification summary to console.
    """
    print("\n" + "=" * 60)
    print("LLM Classification Complete")
    print("=" * 60)

    print(f"\nRun ID: {stats.get('run_id', 'unknown')}")
    print(f"Phrases processed: {stats.get('phrases_processed', 0)}")
    print(f"API calls made: {stats.get('api_calls', 0)}")
    print(f"Errors: {stats.get('errors', 0)}")

    # Token usage
    tokens = stats.get("tokens_used", {})
    if tokens:
        print("\nToken usage by provider:")
        for provider, count in tokens.items():
            print(f"  {provider}: {count:,} tokens")

    # Quintile distribution
    quintiles = stats.get("quintile_distribution", {})
    if quintiles:
        print("\nConfidence quintile distribution:")
        for quintile, count in sorted(quintiles.items()):
            bar = "█" * min(count, 50)
            print(f"  {quintile:20s}: {count:4d} {bar}")

    # Category distribution
    categories = stats.get("category_distribution", {})
    if categories:
        print("\nCategory distribution:")
        for category, count in sorted(categories.items(), key=lambda x: -x[1]):
            bar = "█" * min(count, 50)
            print(f"  {category:20s}: {count:4d} {bar}")

    # Output files
    print(f"\nOutput files written to: {output_dir}")
    print(f"  - classified_{module_name}.tsv")
    print(f"  - llm_run_log.json")
    print()
