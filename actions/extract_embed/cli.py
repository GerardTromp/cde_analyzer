#
# File: actions/extract_embed/cli.py
#
from argparse import ArgumentParser, BooleanOptionalAction
from utils.constants import MODEL_REGISTRY

help_text = "Extract subset of fields from model for embedding text"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action
description_text = """Extract a desired subset of fields and collapse repeated
key:value pairs to key: 'value1;; value2;; value3,...'.

The subset of fields is specified in a file (--path-file) as a set of 
   key-value pairs. Output "flattens" nested dict to simple dict with
   new keys.
   
"""

def register_subparser(subparser: ArgumentParser):
    subparser.add_argument("--input", "-i", help="Input JSON file.")
    # Batch mode: extract embed files for multiple stripped variants at once
    subparser.add_argument(
        "--batch-dir", "-d",
        default=None,
        help="Batch mode: directory containing stripped_*.json files. "
             "Produces both TSV (concatenated embed_text) and CSV (separate columns) "
             "for each variant found. Requires --path-file and -m.",
    )
    subparser.add_argument(
        "--batch-variants",
        default=None,
        help="Comma-separated variant codes to extract in batch mode "
             "(e.g., MTSFPT,MTSTPT). Default: all stripped_*.json found.",
    )
    subparser.add_argument(
        "--embed-separator",
        default=" :--: ",
        help="Separator for TSV concatenation in batch mode (default: ' :--: ').",
    )
#    ids = subparser.add_mutually_exclusive_group()
    subparser.add_argument(
        "--id-list",
        nargs="+",
        # required=True,
        help="List of item IDs (tinyId) to exclude or extract.",
    )
    subparser.add_argument(
        "--id-file",
        # default=str,
        help="File containing list of item IDs (tinyId) to exclude or extract. "
             "Use file:column format to specify column (e.g., 'data.csv:tinyId'). "
             "Cells can contain multiple tinyIds (pipe, comma, or space separated).",
    )
    subparser.add_argument(
        "--id-type", default=None, help="The type of ID, e.g., tinyId."
    )
    subparser.add_argument(
        "--output-format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Choose output format.",
    )
    subparser.add_argument(
        "-o",
        "--output",
        default=str,
        help="Path, including filename, to store results.",
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
    subparser.add_argument(
        "-c",
        "--collapse",
        action=BooleanOptionalAction,
        default=True,
        help='Collapse repeated "None;" in list items.',
    )
    subparser.add_argument(
        "-s",
        "--simplify-permissible",
        action=BooleanOptionalAction,
        default=True,
        help="Process limited set of permissibleValues fields using heuristic.",
    )
    subparser.add_argument(
        "--concatenate",
        default=None,
        metavar="SEP",
        help="Concatenate all non-tinyId fields into a single 'embed_text' column "
             "using SEP as the joining string (e.g., ' | ' or ' [SEP] '). "
             "Forces output format to csv or tsv.",
    )
    subparser.set_defaults(
        _runner="actions.extract_embed.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)