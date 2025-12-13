from argparse import ArgumentParser, BooleanOptionalAction


help_text = "Count occurrences of fields in JSON pydantic model."
description_text = "Count pydantic model fields that satisify certain conditions, including checking for numeric, integer, string and length of string."


def register_subparser(subparser: ArgumentParser):
    subparser.add_argument("--input", help="Input JSON file.")
    subparser.add_argument("--fields", nargs="+", required=True)
    subparser.add_argument(
        "--match-type",
        choices=["non_null", "null", "fixed", "regex"],
        default="non_null",
        help="Type of match, null type is empty string or list, or None.",
    )
    subparser.add_argument(
        "--value", help="Value to match if match-type is fixed or regex."
    )
    subparser.add_argument(
        "--output-format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Output format.",
    )
    subparser.add_argument(
        "--output", help="Path, including filename, to store results."
    )
    subparser.add_argument(
        "--group-by",
        help="Dotted path or key name to group by (e.g. tinyId or path.to.tinyId)",
    )
    subparser.add_argument(
        "--group-type",
        choices=["top", "path", "terminal"],
        default="top",
        help="Interpret group-by field as a top-level, full-path, or terminal (deepest) component of model",
    )
    subparser.add_argument("--logic", help="Logical expression (e.g. 'A and not B')")
    subparser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug output for group-by resolution",
    )
    subparser.add_argument(
        "--count-type",
        action="store_true",
        help="Classify and count field values by type (int, float, strN)",
    )
    subparser.add_argument(
        "--char-limit",
        type=int,
        default=10,
        help="Character limit for short string classification",
    )
    subparser.add_argument(
        "--output-flat",
        action="store_true",
        help="Flatten nested result keys for easier analysis",
    )
    subparser.set_defaults(
        _runner="actions.phrase_builder.run"
    )
    # subparser.set_defaults(func=run_action)

