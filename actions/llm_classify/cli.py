#
# File: actions/llm_classify/cli.py
#
# CLI argument parser for LLM-based phrase classification.
#
from argparse import ArgumentParser, BooleanOptionalAction

help_text = "Classify phrases using multi-LLM queries"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action
description_text = """Agentic LLM-based classification for phrase curation.

Uses multiple LLM providers (Claude, OpenAI, Gemini) to classify phrases
from phrase_miner output into semantic categories. Supports:
  - Multi-LLM querying with result aggregation
  - Confidence quintile ranking
  - Modular query types (instrument detection, temporal patterns)
  - Flexible API key configuration (config file, env vars, CLI)

Example:
  cde_analyzer llm_classify -i phrase_output/ -o llm_output/ --module instrument
  cde_analyzer llm_classify -i phrase_output/ --module temporal --providers claude openai
"""


def register_subparser(subparser: ArgumentParser):
    # Input/Output
    subparser.add_argument(
        "-i", "--input-dir",
        required=True,
        help="Directory containing phrase_miner output files (phrases.tsv, etc.)."
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
        required=True,
        choices=["instrument", "temporal", "instrument_family"],
        help="Query module to use for classification."
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

    subparser.set_defaults(
        _runner="actions.llm_classify.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
