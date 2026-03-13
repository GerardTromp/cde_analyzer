#
# File: actions/llm_classify/cli.py
#
# CLI argument parser for LLM-based phrase classification and proxy generation.
#
from argparse import ArgumentParser, BooleanOptionalAction

help_text = "LLM-based classification and semantic proxy generation"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


description_text = """LLM-based classification and semantic proxy generation.

Uses multiple LLM providers (Claude, OpenAI, Gemini) to classify phrases
from phrase_miner output into semantic categories. Supports:
  - Multi-LLM querying with result aggregation
  - Confidence quintile ranking
  - Modular query types (instrument detection, temporal patterns)
  - Semantic proxy generation (LLM-generated short replacements)
  - Flexible API key configuration (config file, env vars, CLI)

Example:
  cde_analyzer llm_classify -i phrase_output/ -o llm_output/ --module instrument
  cde_analyzer llm_classify -i phrase_output/ --module temporal --providers claude openai
  cde_analyzer llm_classify --generate-proxies patterns.tsv --original-cdes cdes.json \\
      --proxy-output proxied.tsv --providers claude
"""


def register_subparser(subparser: ArgumentParser):
    # Input/Output (classification mode)
    subparser.add_argument(
        "-i", "--input-dir",
        help="Directory containing phrase_miner output files (phrases.tsv, etc.). "
             "Required for classification mode."
    )
    subparser.add_argument(
        "-o", "--output-dir",
        default="llm_output",
        help="Output directory for classification results."
    )
    subparser.add_argument(
        "--original-cdes",
        help="Path to original CDE JSON file for full context retrieval."
    )

    # Query module selection
    subparser.add_argument(
        "-m", "--module",
        choices=["instrument", "temporal", "instrument_family"],
        help="Query module to use for classification. Required for classification mode."
    )
    subparser.add_argument(
        "--reference-file",
        help="Path to reference data file for the module (e.g., known instruments)."
    )

    # Instrument adjudication mode
    subparser.add_argument(
        "--adjudicate-instruments",
        metavar="INSTRUMENTS_TSV",
        help="Path to instruments.tsv for family adjudication. "
             "Reads instruments with needs_review=True and submits to LLM for family classification."
    )
    subparser.add_argument(
        "--adjudicate-threshold",
        type=float,
        default=0.7,
        help="Adjudicate instruments with family_confidence below this threshold."
    )

    # LLM provider configuration
    subparser.add_argument(
        "--providers",
        nargs="+",
        default=["claude"],
        choices=["claude", "openai", "google"],
        help="LLM providers to use."
    )
    subparser.add_argument(
        "--config-file",
        help="Path to LLM config file (auto: ~/.cde_analyzer/llm_config.json)."
    )
    subparser.add_argument(
        "--api-keys",
        nargs="+",
        help="API keys in format 'provider:key' (least preferred method)."
    )

    # Aggregation settings
    subparser.add_argument(
        "--aggregation-method",
        choices=["unanimous", "majority", "weighted_majority", "confidence_weighted"],
        default="majority",
        help="Method for combining multi-LLM results."
    )

    # Processing parameters
    subparser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Number of phrases per LLM batch request."
    )
    subparser.add_argument(
        "--min-frequency",
        type=int,
        default=1,
        help="Minimum phrase frequency to process."
    )
    subparser.add_argument(
        "--context-window",
        type=int,
        default=200,
        help="Characters of context around each phrase occurrence."
    )

    # Working directory and checkpointing
    subparser.add_argument(
        "--working-dir",
        help="Versioned working directory for intermediate files."
    )
    subparser.add_argument(
        "--continue-from",
        help="Resume from a checkpoint file."
    )

    # Validation
    subparser.add_argument(
        "--skip-validation",
        action=BooleanOptionalAction,
        default=False,
        help="Skip API key validation before processing."
    )
    subparser.add_argument(
        "--dry-run",
        action=BooleanOptionalAction,
        default=False,
        help="Load phrases and validate config without making LLM calls."
    )

    # ──────────────────────────────────────────────────────────────
    # Semantic proxy generation mode
    # ──────────────────────────────────────────────────────────────

    subparser.add_argument(
        "--generate-proxies",
        type=str,
        metavar="FILE",
        help="Generate semantic proxies for patterns using an LLM. "
             "Reads a patterns TSV (with pattern and tinyIds columns), "
             "looks up sample CDE contexts from --original-cdes JSON, queries the LLM "
             "for a 1-3 word semantic proxy per pattern, and writes an enriched "
             "TSV with replace_with and proxy_reasoning columns to --proxy-output. "
             "Requires --original-cdes.",
    )
    subparser.add_argument(
        "--proxy-output",
        type=str,
        help="Output file for semantic proxy results (TSV). "
             "Required with --generate-proxies.",
    )
    subparser.add_argument(
        "--cde-model",
        type=str,
        default="CDE",
        help="Model type for parsing CDE JSON (used with --generate-proxies).",
    )
    subparser.add_argument(
        "--llm-model",
        type=str,
        help="LLM model identifier (e.g., claude-sonnet-4-20250514). "
             "Uses provider default if not specified.",
    )
    subparser.add_argument(
        "--fields",
        type=str,
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to scan for context (used with --generate-proxies).",
    )
    subparser.add_argument(
        "--max-contexts",
        type=int,
        default=3,
        help="Maximum CDE contexts to show per pattern (used with --generate-proxies).",
    )

    subparser.set_defaults(
        _runner="actions.llm_classify.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
