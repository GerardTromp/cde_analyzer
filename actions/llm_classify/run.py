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

from utils.file_utils import graceful_interrupt

logger = logging.getLogger(__name__)


@graceful_interrupt
def run_action(args: Namespace):
    """
    Run LLM-based phrase classification or semantic proxy generation.

    Dispatches to classification pipeline or proxy generation based on args.
    """
    # Check for generate-proxies mode first (standalone)
    generate_proxies = getattr(args, 'generate_proxies', None)
    if generate_proxies:
        return _run_generate_proxies(args, generate_proxies)

    # Classification mode: validate required args
    input_dir_raw = getattr(args, 'input_dir', None)
    module = getattr(args, 'module', None)
    if not input_dir_raw:
        print("error: --input-dir is required for classification mode", file=sys.stderr)
        sys.exit(2)
    if not module:
        print("error: --module is required for classification mode", file=sys.stderr)
        sys.exit(2)

    input_dir = Path(input_dir_raw)
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


def _run_generate_proxies(args, input_path: str) -> int:
    """
    Generate semantic proxies for patterns using an LLM.

    Reads a patterns TSV, looks up sample CDE contexts from the source JSON,
    queries an LLM for a 1-3 word semantic proxy per pattern, and writes an
    enriched TSV with replace_with and proxy_reasoning columns.

    This is a wireframe for evaluating whether semantic substitution
    produces meaningful proxies before building a full pipeline.
    """
    import asyncio
    import json
    import re
    from pathlib import Path
    from utils.file_utils import exit_if_missing
    from utils.constants import MODEL_REGISTRY
    from pydantic import ValidationError

    output_path = getattr(args, 'proxy_output', None)
    input_json = getattr(args, 'original_cdes', None)
    if not output_path:
        logger.error("--proxy-output is required for --generate-proxies")
        raise SystemExit(1)
    if not input_json:
        logger.error("--original-cdes (CDE JSON) is required for --generate-proxies")
        raise SystemExit(1)

    exit_if_missing(input_path, "Patterns TSV")
    exit_if_missing(input_json, "Input JSON")

    provider_name = args.providers[0] if args.providers else 'claude'
    llm_model = getattr(args, 'llm_model', None)
    config_file = getattr(args, 'config_file', None)
    api_keys = getattr(args, 'api_keys', None)
    context_window = getattr(args, 'context_window', 150)
    max_contexts = getattr(args, 'max_contexts', 3)
    dry_run = getattr(args, 'dry_run', False)
    model_name = getattr(args, 'cde_model', 'CDE')
    field_paths = getattr(args, 'fields',
                          ["definitions.*.definition", "designations.*.designation"])

    # --- Load patterns TSV ---
    rows = []  # (fields_list, pattern, tinyids_set)
    with open(input_path, encoding="utf-8") as f:
        header_line = f.readline().strip()
        headers = header_line.split('\t')

        from utils.pattern_tsv_utils import find_column_index
        pattern_idx = find_column_index(headers, 'pattern')
        tinyids_idx = find_column_index(headers, 'tinyIds')

        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            fields = line.split('\t')
            pattern = fields[pattern_idx].strip().strip('"') if pattern_idx < len(fields) else ""
            tinyids_str = fields[tinyids_idx].strip().strip('"') if tinyids_idx < len(fields) else ""
            tinyids = set(t for t in re.split(r'[\s|]+', tinyids_str) if t)
            rows.append((fields, pattern, tinyids))

    logger.info(f"Loaded {len(rows)} patterns from {input_path}")

    # --- Load CDE JSON for context ---
    model_class = MODEL_REGISTRY[model_name]
    with open(input_json, encoding="utf-8") as f:
        data = json.load(f)

    try:
        parsed = [model_class.model_validate(obj) for obj in data]
    except ValidationError as e:
        for error in e.errors():
            logger.error(f"{error['type']}: {error['msg']} at {error['loc']}")
        raise SystemExit(1)

    logger.info(f"Loaded {len(parsed)} CDE records from {input_json}")

    # Build tinyId -> record lookup
    tid_to_record = {}
    for rec in parsed:
        if hasattr(rec, 'tinyId') and rec.tinyId:
            tid_to_record[rec.tinyId] = rec

    # --- Extract contexts per pattern ---
    from logic.verbatim_discoverer import _extract_at_path

    def _get_contexts(pattern: str, tinyids: set) -> str:
        """Find sample CDE texts containing this pattern."""
        contexts = []
        # Search in tinyId-restricted records first, fall back to all records
        search_records = [tid_to_record[t] for t in tinyids if t in tid_to_record] if tinyids else parsed
        for rec in search_records[:20]:  # limit search scope
            rec_dict = rec.model_dump(mode="json")
            for fp in field_paths:
                parts = fp.split('.')
                texts = _extract_at_path(rec_dict, parts)
                for text in texts:
                    idx = text.lower().find(pattern.lower())
                    if idx >= 0:
                        start = max(0, idx - context_window)
                        end = min(len(text), idx + len(pattern) + context_window)
                        snippet = text[start:end]
                        # Mark the pattern in context
                        field_label = fp.rsplit('.', 1)[-1]
                        contexts.append(f"  [{field_label}] ...{snippet}...")
                        if len(contexts) >= max_contexts:
                            break
                if len(contexts) >= max_contexts:
                    break
            if len(contexts) >= max_contexts:
                break
        return "\n".join(contexts) if contexts else "(no context found)"

    # --- Build query module and LLM provider ---
    from utils.query_modules import get_module
    module = get_module("semantic_proxy")
    system_prompt = module.build_system_prompt()
    user_template = module.build_user_prompt_template()

    if dry_run:
        # Show prompts for first 3 patterns without calling LLM
        print("\n=== DRY RUN: Showing prompts (no LLM calls) ===\n")
        print(f"System prompt ({len(system_prompt)} chars):")
        print(system_prompt[:500] + "...\n")
        for i, (fields_list, pattern, tinyids) in enumerate(rows[:3]):
            context_text = _get_contexts(pattern, tinyids)
            user_prompt = user_template.format(
                phrase_text=pattern,
                context_section=f"Sample CDE contexts:\n{context_text}",
            )
            print(f"--- Pattern {i+1}: '{pattern[:60]}' ---")
            print(user_prompt)
            print()
        print(f"(Showing 3 of {len(rows)} patterns)")
        return 0

    # --- Resolve LLM config and create provider ---
    from utils.llm import resolve_config, create_provider

    config_file_path = Path(config_file) if config_file else None
    llm_config = resolve_config(
        requested_providers=[provider_name],
        config_file_path=config_file_path,
        cli_api_keys=api_keys,
    )

    provider_config = llm_config.get_providers()[0]
    if llm_model:
        provider_config.model = llm_model

    provider = create_provider(provider_config)
    logger.info(f"Using {provider.provider_name} (model: {provider.model_id})")

    # --- Query LLM for each pattern ---
    from CDE_Schema.LLM_Classification import PhraseContext

    results = []  # list of (proxy, confidence, reasoning)

    async def _query_one(pattern: str, tinyids: set) -> tuple:
        context_text = _get_contexts(pattern, tinyids)
        phrase = PhraseContext(
            phrase_text=pattern,
            verbatim_forms=[pattern],
            field_contexts=[],
            frequency=len(tinyids),
            n_tinyids=len(tinyids),
        )

        responses = await provider.classify_batch(
            phrases=[phrase],
            system_prompt=system_prompt,
            user_prompt_template=user_template.replace(
                "{context_section}",
                f"Sample CDE contexts:\n{context_text}",
            ),
            categories=module.output_categories,
        )
        if responses:
            resp = responses[0]
            # The "category" field holds the raw LLM text for proxy modules
            proxy, confidence, reasoning = module.parse_response(
                resp.raw_response if hasattr(resp, 'raw_response') and resp.raw_response
                else f'{{"proxy": "{resp.category}", "confidence": {resp.confidence}, "reasoning": "{resp.reasoning}"}}'
            )
            return proxy, confidence, reasoning
        return "", 0.0, "No response from LLM"

    async def _run_all():
        for i, (fields_list, pattern, tinyids) in enumerate(rows):
            if not pattern:
                results.append(("", 0.0, ""))
                continue
            print(f"  [{i+1}/{len(rows)}] {pattern[:60]}...", end="", flush=True)
            try:
                proxy, confidence, reasoning = await _query_one(pattern, tinyids)
                results.append((proxy, confidence, reasoning))
                print(f" -> '{proxy}' ({confidence:.2f})")
            except Exception as e:
                logger.warning(f"LLM error for pattern '{pattern[:40]}': {e}")
                results.append(("", 0.0, f"ERROR: {e}"))
                print(f" -> ERROR: {e}")

    print(f"\nGenerating proxies for {len(rows)} patterns...")
    asyncio.run(_run_all())

    # --- Write output TSV ---
    # Remove existing replace_with/proxy_reasoning columns if re-running
    proxy_cols = {"replace_with", "proxy_reasoning", "proxy_confidence"}
    clean_header_indices = [i for i, h in enumerate(headers) if h not in proxy_cols]
    clean_headers = [headers[i] for i in clean_header_indices]
    out_headers = clean_headers + ["replace_with", "proxy_confidence", "proxy_reasoning"]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\t".join(out_headers) + "\n")
        for idx, (fields_list, pattern, tinyids) in enumerate(rows):
            clean_fields = [fields_list[i] if i < len(fields_list) else ""
                            for i in clean_header_indices]
            proxy, confidence, reasoning = results[idx] if idx < len(results) else ("", 0.0, "")
            # Escape tabs in reasoning
            reasoning_clean = reasoning.replace('\t', ' ').replace('\n', ' ')
            row = clean_fields + [proxy, f"{confidence:.2f}", reasoning_clean]
            f.write("\t".join(row) + "\n")

    # Summary
    successful = sum(1 for p, c, r in results if p)
    high_conf = sum(1 for p, c, r in results if p and c >= 0.7)
    print(f"\nProxy generation complete:")
    print(f"  Input:      {len(rows)} patterns")
    print(f"  Proxied:    {successful} ({successful*100//max(len(rows),1)}%)")
    print(f"  High-conf:  {high_conf} (>= 0.7)")
    print(f"  Wrote:      {output_path}")
    print(f"\nNext steps:")
    print(f"  1. Review {output_path} — edit replace_with column as needed")
    print(f"  2. Apply: cde-analyzer strip_phrases -i INPUT.json --patterns {output_path} --clean-remnants --diff -o OUTPUT.json")

    return 0


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
