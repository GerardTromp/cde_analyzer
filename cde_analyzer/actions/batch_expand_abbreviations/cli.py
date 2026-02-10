"""
Batch Abbreviation Expansion - Discover extended instrument phrases from abbreviations.

Iterates over abbreviations from instrument mining output, subsets CDEs containing
each abbreviation, and mines phrases to discover the full instrument names.

Example:
    PROMIS → "Patient-Reported Outcome Measure Information System"
    PHQ → "Patient Health Questionnaire"
    SF-36 → "36-Item Short Form Health Survey"

This action automates the loop that would otherwise require running
abbreviation_expander.yaml multiple times.
"""

from argparse import ArgumentParser

help_text = "Batch expand abbreviations to discover full instrument phrases"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    """Register arguments for batch_expand_abbreviations action"""

    # Input files
    subparser.add_argument(
        "--input", "-i",
        required=True,
        help="Input CDE JSON file to search for extended phrases"
    )
    subparser.add_argument(
        "--abbreviations",
        required=True,
        help="TSV file with abbreviations (from instrument_miner). "
             "Uses 'acronym' column by default, or specify with --acronym-column"
    )
    subparser.add_argument(
        "--acronym-column",
        default="acronym",
        help="Column name containing abbreviations (default: acronym)"
    )

    # Output
    subparser.add_argument(
        "--output-dir", "-o",
        default="abbreviation_expansions",
        help="Output directory for expansion results (default: abbreviation_expansions)"
    )

    # Fields to search
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["designation", "definition"],
        help="Fields to search for abbreviations (default: designation definition). "
             "Also supports: valueMeaningName, valueMeaningDefinition"
    )

    # Phrase mining parameters
    subparser.add_argument(
        "--k-max",
        type=int,
        default=15,
        help="Maximum k-mer length for phrase mining (default: 15)"
    )
    subparser.add_argument(
        "--k-min",
        type=int,
        default=3,
        help="Minimum k-mer length for phrase mining (default: 3)"
    )
    subparser.add_argument(
        "--min-tinyids",
        type=int,
        default=2,
        help="Minimum distinct tinyIds for phrase to be reported (default: 2)"
    )
    subparser.add_argument(
        "--top-phrases",
        type=int,
        default=10,
        help="Number of top phrases to report per abbreviation (default: 10)"
    )

    # Filtering
    subparser.add_argument(
        "--min-subset-size",
        type=int,
        default=3,
        help="Minimum CDEs in subset to run phrase mining (default: 3). "
             "Abbreviations with fewer matches are skipped."
    )
    subparser.add_argument(
        "--skip-abbreviations",
        nargs="+",
        help="Abbreviations to skip (e.g., common false positives)"
    )

    # Set defaults
    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
