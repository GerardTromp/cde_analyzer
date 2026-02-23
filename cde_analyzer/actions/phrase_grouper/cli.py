"""
Phrase Grouper - Bottom-up k-mer analysis for phrase family discovery.

Analyzes verbatim phrases from phrase_miner output to discover structural
patterns that group phrases into families. Builds three independent trees:
- Prefix families: phrases sharing common beginnings
- Suffix families: phrases sharing common endings
- Infix families: phrases sharing common internal patterns

Uses bottom-up k-mer construction starting from small k (2-3 tokens) and
extending upward to find maximal shared patterns. Frequency determines
which tree provides the best family assignment for each phrase.

This complements the top-down phrase_miner approach:
- phrase_miner: "What are the longest repeated phrases?"
- phrase_grouper: "What patterns do the found phrases share?"
"""

from argparse import ArgumentParser

help_text = "Bottom-up k-mer analysis for phrase family discovery"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    """Register arguments for phrase_grouper action"""

    # Input/Output
    subparser.add_argument(
        "--input", "-i",
        required=True,
        help="Input TSV file (verbatim_phrases.tsv from phrase_miner)"
    )
    subparser.add_argument(
        "--output-dir", "-o",
        default="phrase_families",
        help="Output directory for results"
    )

    # Column selection (for flexible input formats)
    subparser.add_argument(
        "--text-column",
        default="verbatim_text",
        help="Column name containing phrase text"
    )
    subparser.add_argument(
        "--id-column",
        default="phrase_id",
        help="Column name for phrase identifier"
    )
    subparser.add_argument(
        "--tinyid-column",
        default="tinyids",
        help="Column name for document IDs"
    )

    # K-mer parameters
    subparser.add_argument(
        "--k-min", "-k",
        type=int,
        default=3,
        help="Minimum k-mer length in tokens"
    )
    subparser.add_argument(
        "--k-max", "-K",
        type=int,
        default=10,
        help="Maximum k-mer length in tokens"
    )
    subparser.add_argument(
        "--min-content-words",
        type=int,
        default=1,
        help="Minimum non-stopword tokens required in pattern. "
             "Filters patterns like 'of the' that are entirely stopwords."
    )

    # Family filtering
    subparser.add_argument(
        "--min-family-size", "-n",
        type=int,
        default=3,
        help="Minimum phrases to form a family"
    )
    subparser.add_argument(
        "--min-pattern-freq",
        type=int,
        default=3,
        help="Minimum frequency for pattern to be considered"
    )

    # Tree selection
    subparser.add_argument(
        "--trees",
        nargs="+",
        choices=["prefix", "suffix", "infix"],
        default=["prefix", "suffix", "infix"],
        help="Which trees to build"
    )

    # Assignment strategy
    subparser.add_argument(
        "--assignment",
        choices=["frequency", "longest", "all"],
        default="frequency",
        help="How to assign phrases to families when multiple match: "
             "frequency (highest pattern frequency wins), "
             "longest (longest matching pattern wins), "
             "all (report all matches). Default: frequency"
    )

    # Processing options
    subparser.add_argument(
        "--parallel",
        action="store_true",
        help="Build trees in parallel (uses multiprocessing)"
    )
    subparser.add_argument(
        "--lowercase",
        action="store_true",
        help="Normalize phrases to lowercase before analysis"
    )

    # Set defaults
    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
