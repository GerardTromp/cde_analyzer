#
# File: actions/subset/cli.py
#
from argparse import ArgumentParser, BooleanOptionalAction
from utils.constants import MODEL_REGISTRY

help_text = "Extract a subset of CDE records by tinyId or text content"


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


description_text = """Filter CDE or Form records by tinyId list or text content and output
a smaller, schema-compliant JSON file. Useful for:
  - Creating focused datasets for specific analyses
  - Reducing file size for faster processing
  - Isolating records of interest from large CDE exports
  - Extracting records containing specific text patterns (e.g., instrument abbreviations)

Two filtering modes:
  1. tinyId filtering: --id-list or --id-file (include/exclude specific records)
  2. Text filtering: --text-filter with --fields (search for text in specific fields)
"""


def register_subparser(subparser: ArgumentParser):
    # Input/Output
    subparser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input JSON file."
    )
    subparser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output file."
    )
    subparser.add_argument(
        "-m", "--model",
        required=True,
        choices=MODEL_REGISTRY.keys(),
        help="Pydantic model for validation (CDE, Form, EmbedText)."
    )
    subparser.add_argument(
        "--output-format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Output format."
    )

    # tinyId filtering - file or CLI list
    subparser.add_argument(
        "--id-list", "-l",
        nargs="+",
        help="List of tinyIds to include or exclude."
    )
    subparser.add_argument(
        "--id-file", "-L",
        help="File containing tinyIds (JSON, CSV, or TSV). "
             "Use file:column format to specify column (e.g., 'data.csv:tinyId'). "
             "Cells can contain multiple tinyIds (pipe, comma, or space separated)."
    )

    # Text-based filtering
    subparser.add_argument(
        "--text-filter", "-t",
        help="Text pattern to search for in specified fields. "
             "Records containing this text will be included (or excluded with --exclude)."
    )
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["designation", "definition"],
        help="Fields to search for text filter. "
             "Also supports: valueMeaningName, valueMeaningDefinition"
    )
    subparser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Make text filter case-sensitive."
    )
    subparser.add_argument(
        "--regex",
        action="store_true",
        help="Treat --text-filter as a regular expression pattern."
    )

    # Multi-pattern filtering from file (like grep -f)
    subparser.add_argument(
        "--pattern-file", "-F",
        help="File containing regex patterns (one per line). "
             "Like grep -E -f, matches records against any pattern. "
             "Format: 'pattern' or 'pattern<TAB>label' for grouping."
    )
    subparser.add_argument(
        "--match-report",
        help="Output file for detailed match report (TSV with tinyId, matched patterns, labels)."
    )
    subparser.add_argument(
        "--tinyid-report",
        help="Output file listing matched tinyIds only (one per line, for pipeline chaining)."
    )

    # Include/Exclude mode
    subparser.add_argument(
        "--exclude", "-x",
        action=BooleanOptionalAction,
        default=False,
        help="Exclude matching records (--exclude) or include them (--no-exclude, default). "
             "Works with both tinyId and text filtering."
    )

    subparser.set_defaults(
        _runner="actions.subset.run"
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)