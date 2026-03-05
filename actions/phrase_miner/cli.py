"""
Phrase Miner - Iterative k-mer phrase detection with de Bruijn extension.

Detects repeated multi-word phrases using descending k-mer mining (k=25 to k=3)
with de Bruijn graph extension, subsumption filtering, and optional anchor extension.

For instrument extraction, use the dedicated `instrument_miner` action instead.
This action focuses on general phrase mining from CDE text fields.

Implemented features:
- Core k-mer mining with iterative descent (Phase 1-3)
- Frequency and tinyId filtering
- Aho-Corasick multi-pattern matching for efficient masking (Phase 4)
- De Bruijn graph contig extension for phrase merging (Phase 5)
- Verbatim text recovery for original surface forms (Phase 3.5)
- Subsumption filtering to remove redundant shorter phrases (Phase 6)
- Anchor-based phrase extension using context bigrams (Phase 7)
"""

from argparse import ArgumentParser, BooleanOptionalAction

help_text = "Iterative phrase mining using descending k-mers and masking"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


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
        help="Output directory for results"
    )

    # Field selection (reuse existing pattern from phrase action)
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["designation", "definition"],
        help="Field names to extract phrases from. "
             "Also supports: valueMeaningName, valueMeaningDefinition"
    )

    # K-mer parameters
    subparser.add_argument(
        "--k-max", "-K",
        type=int,
        default=25,
        help="Maximum k-mer length"
    )
    subparser.add_argument(
        "--k-min", "-k",
        type=int,
        default=3,
        help="Minimum k-mer length"
    )
    subparser.add_argument(
        "--freq-min", "-n",
        type=int,
        default=3,
        help="Minimum frequency threshold per k-bin"
    )
    subparser.add_argument(
        "--min-tinyids", "-t",
        type=int,
        default=2,
        help="Minimum distinct tinyIds (document support)"
    )

    # Text processing (match existing actions)
    subparser.add_argument(
        "--lemmatize",
        action=BooleanOptionalAction,
        default=True,
        help="Apply lemmatization to tokens (use --no-lemmatize to disable)"
    )
    subparser.add_argument(
        "--remove-stopwords",
        action="store_true",
        help="Remove English stopwords during tokenization"
    )

    # Algorithm stages
    subparser.add_argument(
        "--skip-debruijn",
        action="store_true",
        help="Skip de Bruijn contig extension (enabled by default)"
    )
    subparser.add_argument(
        "--enable-debruijn", "-D",
        action="store_true",
        help="Enable de Bruijn graph extension to merge overlapping k-mers into longer phrases"
    )
    subparser.add_argument(
        "--enable-subsumption", "-S",
        action="store_true",
        help="Enable subsumption filtering to remove shorter phrases contained in longer ones"
    )
    subparser.add_argument(
        "--skip-anchor",
        action="store_true",
        help="Skip anchor-based extension (use with --enable-anchor to disable it again)"
    )
    subparser.add_argument(
        "--enable-anchor",
        action="store_true",
        help="Enable anchor-based phrase extension using context bigrams"
    )
    subparser.add_argument(
        "--no-aho-corasick",
        action="store_true",
        help="Use naive pattern matching instead of Aho-Corasick (slower, for debugging)"
    )
    subparser.add_argument(
        "--dedup",
        action="store_true",
        default=True,
        help="Enable whole-text dedup pre-pass before k-mer mining. "
             "Detects field texts shared by multiple CDEs and emits them as phrases, "
             "then masks them to prevent redundant k-mer fragment detection.",
    )
    subparser.add_argument(
        "--no-dedup",
        dest="dedup",
        action="store_false",
        help="Disable whole-text dedup pre-pass.",
    )
    subparser.add_argument(
        "--dedup-min-count",
        type=int,
        default=2,
        help="Minimum CDEs sharing identical text for dedup emission.",
    )
    subparser.add_argument(
        "--dedup-min-tokens",
        type=int,
        default=3,
        help="Minimum tokens in dedup text to emit as phrase.",
    )

    # Verbatim output options
    subparser.add_argument(
        "--verbatim-case-sensitive",
        action="store_true",
        help="Use case-sensitive comparison for verbatim subsumption (preserves case variants for QC)"
    )

    # Phrase family analysis (post-mining analysis of non-instrument phrases)
    subparser.add_argument(
        "--analyze-phrase-families",
        action="store_true",
        help="Analyze extracted phrases for family groupings using prefix/suffix patterns. "
             "Outputs phrase_families.tsv and phrase_family_members.tsv."
    )
    subparser.add_argument(
        "--min-prefix-words",
        type=int,
        default=2,
        help="Minimum words for prefix pattern detection"
    )
    subparser.add_argument(
        "--min-suffix-words",
        type=int,
        default=1,
        help="Minimum words for suffix pattern detection"
    )
    subparser.add_argument(
        "--min-family-size",
        type=int,
        default=3,
        help="Minimum number of phrases to form a family"
    )
    subparser.add_argument(
        "--max-families",
        type=int,
        default=100,
        help="Maximum number of families to report"
    )

    # Prefix consolidation (post-loop recovery of fragmented prefixes)
    subparser.add_argument(
        "--prefix-consolidation",
        action=BooleanOptionalAction,
        default=True,
        help="Detect common prefixes across mined phrases and emit them as "
             "additional phrases when aggregate tinyId coverage exceeds "
             "--prefix-min-tinyids. Use --no-prefix-consolidation to disable.",
    )
    subparser.add_argument(
        "--prefix-min-tinyids",
        type=int,
        default=20,
        help="Minimum union tinyId count for a prefix to be emitted "
             "during consolidation. Default: 20.",
    )
    subparser.add_argument(
        "--prefix-min-descendants",
        type=int,
        default=3,
        help="Minimum distinct longer phrases sharing a prefix for "
             "consolidation. Default: 3.",
    )

    # Ledger-informed pre-masking
    subparser.add_argument(
        "--ledger-dir",
        type=str,
        default=None,
        help="Curation ledger directory. If provided, 'remove' decisions are "
             "pre-masked during mining to reduce search space.",
    )

    # Optional features
    subparser.add_argument(
        "--histograms",
        action="store_true",
        help="Generate k-mer frequency histograms in output_dir/histograms/ (requires matplotlib)"
    )

    # Set defaults
    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
