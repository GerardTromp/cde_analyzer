#
# File: actions/lemma_fasta/cli.py
#
from utils.constants import MODEL_REGISTRY
from argparse import ArgumentParser, BooleanOptionalAction

help_text = "Extract fields as pseudo FASTA format"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action
description_text = """Extract a desired subset of fields as for embedding 
(extract_embed), but encode the "words" as uint16_t tokens to be used by 
genomic repeat finder tools.

The subset of fields is specified in a file (--path-file) as a set of 
   key-value pairs. Output "flattens" nested dict to simple dict with
   new keys.
The encoded uint16_t tokens are written to a fasta file encoding the 
   binary values in base85. The genomic tools need to be modified to
   de-/en- code the base85 data and work with uint16 tokens. 
Multiple files are generated so that the output name must be a stem/prefix. 
   1. JSON with keys:
      a. lemmatized -- JSON of simplified model, text lemmatized
      b. verbatim   -- JSON of simplified model, text original
      c. b85        -- JSON with base85 concatenated strings for each value
      d. b85_concat -- JSON base 85 of single `fasta_uint16` key (in addtion to tinyId)
      d. vocab      -- Vocab dict of lemmatized words and corresponding
                       uint16 encoding
   2. Pseudo fasta:
      a. FASTA representaiton of 1.b. > tinyid and base85 string as 
         payload
"""

def register_subparser(subparser: ArgumentParser):
    subparser.add_argument("--input", "-i", required=True, help="Input JSON file.")
    ids = subparser.add_mutually_exclusive_group()
    ids.add_argument(
        "--id-list",
        nargs="+",
        # required=True,
        help="List of item IDs (tinyId) to exclude or extract.",
    )
    ids.add_argument(
        "--id-file",
        default=str,
        help="File containing list of item IDs (tinyId) to exclude or extract. "
             "Use file:column format to specify column (e.g., 'data.csv:tinyId'). "
             "Cells can contain multiple tinyIds (pipe, comma, or space separated).",
    )
    subparser.add_argument(
        "--id-type", default=str, help="The type of ID (default=tinyId)."
    )
    subparser.add_argument(
        "-o",
        "--output",
        default=str,
        help="Path, with a prefix/stem name for results. Multiple files will be generated",
    )
    subparser.add_argument(
        "--output-format",
        choices=["pfasta", "lfasta"],
        default="pfasta",
        help="Choose output format (default 'pfasta')",
    )
    subparser.add_argument(
        "-m",
        "--model",
        default=str,
        required=True,
        choices=MODEL_REGISTRY.keys(),
        help="pydantic model appropriate for input file. ",
    )
    subparser.add_argument(
        "--path-file",
        default=str,
        help="File with paths of interest and new name (as name:path) for extracted data.",
    )
    subparser.add_argument(
        "--exclude",
        action=BooleanOptionalAction,
        default=True,
        help="Exclude (--exclude) or include (--no-exclude) IDs in list.",
    )
    subparser.add_argument( # Need to add the logic yet 
        "--remove-spaces",
        action=BooleanOptionalAction,
        default=True,
        help="Remove spaces, return lemmatized content as string with no spaces (default=True)",
    )
    subparser.add_argument(
        "--remove-stopwords",
        action="store_true",
        help="Remove common English stop words (articles, prepositions, conjunctions)?",
    )
    subparser.add_argument(
        "--min-freq",
        default=1,
        type=int,
        help="What is the minimum number of occurrences to encode uint16. Freq <= min-freq will be 0x00"
    )
    
    subparser.set_defaults(
        _runner="actions.lemma_fasta.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)