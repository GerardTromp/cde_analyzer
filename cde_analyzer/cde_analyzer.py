#! /usr/bin/python3
import sys
import argparse
import importlib
from utils.logger import configure_logging
from utils.analyzer_state import get_verbosity, set_verbosity

# --------------------------------------------------------------------
# MAX-LAZY ACTION REGISTRATION
# --------------------------------------------------------------------
# No action modules are imported at startup.
# Each action has a module path + static help metadata.
# Action modules will be loaded ONLY when invoked by the user.
# --------------------------------------------------------------------

ACTION_REGISTRY = {
    "fix_underscores": {
        "module": "actions.fix_underscores.cli",
        "help": "Fix variables that start with underscores in CDE fields",
        "description": "Underscores are not permitted in 'pydantic' name tags",
    },
    "strip_html": {
        "module": "actions.strip_html.cli",
        "help": "Strip HTML tags from fields",
        "description": "Remove HTML markup in CDE values",
    },
    "phrase": {
        "module": "actions.phrase.cli",
        "help": "Find repeated phrases",
        "description": "Phrase analysis utilities for CDE data",
    },
    "count": {
        "module": "actions.count.cli",
        "help": "Count structural elements",
        "description": "Count fields, occurrences, and other metrics",
    },
    "extract_embed": {
        "module": "actions.extract_embed.cli",
        "help": "Extract desired fields and save in format for 'transformer' embedding",
        "description": "Flexible extraction of nested Pydantic values and export to format compatible with 'transformers'",
    },
    "strip_phrases": {
        "module": "actions.strip_phrases.cli",
        "help": "Remove literal phrases at given paths",
        "description": "Literal search-and-replace on structured data",
    },
    "lemma_fasta": {
        "module": "actions.lemma_fasta.cli",
        "help": "Create FASTA from lemma sequences",
        "description": "Convert lemma segments into FASTA format",
    },
    "phrase_builder": {
        "module": "actions.phrase_builder.cli",
        "help": "Construct phrase models",
        "description": "Incremental phrase builder for CDE analysis",
    },
    "subset": {
        "module": "actions.subset.cli",
        "help": "Extract subset from JSON base on literal, regex, or list of tinyID",
        "description": "Utility to do local searches of JSON files",
    },    
    # "depth": {...}
    # "quality": {...}
}


# --------------------------------------------------------------------
# Helper: Load a module only when needed
# --------------------------------------------------------------------
def load_action_module(module_path: str):
    return importlib.import_module(module_path)


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Utilities to work with the NLM CDE repository data modeled as Pydantic classes"
    )
    parser.add_argument(
        "--verbosity",
        "-v",
        action="count",
        default=1,
        help="Increase verbosity level (-vv for debug)",
    )
    parser.add_argument("--logfile", help="Optional log file path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---------------------------------------------------------------
    # MAX-LAZY subparser creation
    # No action modules imported here.
    # Each subparser simply records the module path.
    # ---------------------------------------------------------------
    for action_name, meta in ACTION_REGISTRY.items():
        action_parser = subparsers.add_parser(
            action_name,
            help=meta["help"],
            description=meta["description"],
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        # Store the module path for lazy loading
        action_parser.set_defaults(_module_path=meta["module"])

        # Minimal lazy registration:
        # We load the module ONLY to let it define its args.
        # If you want *absolute* max-lazy (zero imports even here),
        # then store arg specs in ACTION_REGISTRY and build them dynamically.
        #
        # This version imports the module ONLY to call register_subparser,
        # which is typically small/lightweight.
        module = load_action_module(meta["module"])
        module.register_subparser(action_parser)

    # ---------------------------------------------------------------
    # Parse args now that subparsers are ready
    # ---------------------------------------------------------------
    args = parser.parse_args()

    configure_logging(args.verbosity, args.logfile)
    set_verbosity(args.verbosity)

    # ---------------------------------------------------------------
    # Runtime: Import and run only the chosen action
    # ---------------------------------------------------------------
    if hasattr(args, "_module_path"):
        module = load_action_module(args._module_path)

        if not hasattr(args, "func"):
            raise RuntimeError(
                f"Action module {args._module_path} failed to set args.func in register_subparser()"
            )

        # Run the action
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
