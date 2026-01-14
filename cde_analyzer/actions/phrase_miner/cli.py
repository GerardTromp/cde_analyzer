"""
Phrase Miner - Iterative k-mer phrase detection with de Bruijn extension.

Detects repeated multi-word phrases using descending k-mer mining (k=25 to k=3)
with de Bruijn graph extension, subsumption filtering, and optional anchor extension.

Initial implementation (Phase 1-3) includes:
- Core k-mer mining with iterative descent
- Frequency and tinyId filtering
- Basic masking to prevent re-detection

Future enhancements (Phase 4+):
- Aho-Corasick multi-pattern matching
- De Bruijn graph contig extension
- Subsumption filtering
- Anchor-based phrase extension
"""

from argparse import ArgumentParser, BooleanOptionalAction
from .run import run_action

help_text = "Iterative phrase mining using descending k-mers and masking"
description_text = __doc__


def register_subparser(subparser: ArgumentParser):
    """Register arguments for phrase_miner action"""

    # Input/Output (follow existing pattern)
    subparser.add_argument(
        "--input", "-i",
        required=True,
        help="Input JSON file (list of CDE items)"
    )
    subparser.add_argument(
        "--output-dir", "-o",
        default="phrase_output",
        help="Output directory for results (default: phrase_output)"
    )

    # Field selection (reuse existing pattern from phrase action)
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["designation", "definition"],
        help="Field names to extract phrases from (default: designation definition)"
    )

    # K-mer parameters
    subparser.add_argument(
        "--k-max",
        type=int,
        default=25,
        help="Maximum k-mer length (default: 25)"
    )
    subparser.add_argument(
        "--k-min",
        type=int,
        default=3,
        help="Minimum k-mer length (default: 3)"
    )
    subparser.add_argument(
        "--freq-min",
        type=int,
        default=3,
        help="Minimum frequency threshold per k-bin (default: 3)"
    )
    subparser.add_argument(
        "--min-tinyids",
        type=int,
        default=2,
        help="Minimum distinct tinyIds (document support) (default: 2)"
    )

    # Text processing (match existing actions)
    subparser.add_argument(
        "--lemmatize",
        action=BooleanOptionalAction,
        default=True,
        help="Apply lemmatization to tokens (default: True, creates --no-lemmatize)"
    )
    subparser.add_argument(
        "--remove-stopwords",
        action="store_true",
        help="Remove English stopwords during tokenization"
    )

    # Algorithm stages (for future enhancements)
    subparser.add_argument(
        "--skip-debruijn",
        action="store_true",
        help="Skip de Bruijn contig extension (deferred to Phase 5+)"
    )
    subparser.add_argument(
        "--skip-anchor",
        action="store_true",
        help="Skip anchor-based extension (deferred to Phase 7+)"
    )

    # Optional features
    subparser.add_argument(
        "--histograms",
        action="store_true",
        help="Generate k-mer frequency histograms (requires matplotlib, not yet implemented)"
    )

    # Set defaults
    subparser.set_defaults(func=run_action)
