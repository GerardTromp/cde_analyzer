"""
Instrument Miner - Extract measurement instruments from CDE text fields.

Detects instrument patterns from "as part of <Instrument>" phrases in CDE
designation and definition fields. Supports:
- Title Case instrument extraction
- Abbreviation-only extraction (e.g., "as part of (PHQ-9)")
- Supplementary patterns from config (animal tests, behavioral scales)
- Instrument family detection and assignment

This is Phase 1 of the instrument stripping workflow. Output feeds into
strip_discover for verbatim pattern discovery.
"""

from argparse import ArgumentParser, BooleanOptionalAction

help_text = "Extract measurement instruments from CDE text fields"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    """Register arguments for instrument_miner action"""

    # Input/Output
    subparser.add_argument(
        "--input", "-i",
        required=True,
        help="Input JSON file (list of CDE items)"
    )
    subparser.add_argument(
        "--output-dir", "-o",
        default="instrument_output",
        help="Output directory for results"
    )

    # Field selection
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["designation", "definition"],
        help="Field names to extract instruments from. "
             "Also supports: valueMeaningName, valueMeaningDefinition"
    )

    # Filtering
    subparser.add_argument(
        "--min-tinyids",
        type=int,
        default=2,
        help="Minimum distinct tinyIds (document support)"
    )
    subparser.add_argument(
        "--min-instrument-words",
        type=int,
        default=3,
        help="Minimum words required in instrument name"
    )

    # Extraction modes
    subparser.add_argument(
        "--extract-abbreviation-only", "-a",
        action="store_true",
        help="Extract abbreviation-only instrument references like 'as part of (PHQ-9)'. "
             "Uses known acronyms from first pass to map to canonical instrument names."
    )
    subparser.add_argument(
        "--extract-supplementary", "-s",
        action="store_true",
        help="Extract non-Title-Case instruments (animal models, behavioral tests). "
             "Matches known supplementary patterns from config/supplementary_patterns.yaml."
    )

    # Instrument family detection
    subparser.add_argument(
        "--detect-families", "-d",
        action="store_true",
        help="Enable instrument family detection (groups instruments by family, e.g., Neuro-QOL, PROMIS)"
    )
    subparser.add_argument(
        "--family-confidence-threshold",
        type=float,
        default=0.7,
        help="Minimum confidence for automatic family assignment. "
             "Below threshold, instruments are flagged for review."
    )
    subparser.add_argument(
        "--family-summary",
        action="store_true",
        help="Generate instrument_families.tsv summary file (groups by family)"
    )

    # Set defaults
    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
