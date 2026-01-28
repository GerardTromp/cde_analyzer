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
    "strip_discover": {
        "module": "actions.strip_discover.cli",
        "help": "Discover instrument patterns in CDE text fields",
        "description": "Flexible regex discovery for pattern curation workflow",
    },
    "strip_analyze": {
        "module": "actions.strip_analyze.cli",
        "help": "Analyze patterns for conflicts and false negatives",
        "description": "Pattern analysis utilities for conflict detection and iterative improvement",
    },
    "pattern_util": {
        "module": "actions.pattern_util.cli",
        "help": "TSV pattern utilities (merge, coalesce, import)",
        "description": "Manipulate pattern TSV files without CDE input",
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
    "phrase_miner": {
        "module": "actions.phrase_miner.cli",
        "help": "Iterative k-mer phrase mining with de Bruijn extension",
        "description": "Detects repeated phrases using descending k-mer mining (k=25 to k=3)",
    },
    "instrument_miner": {
        "module": "actions.instrument_miner.cli",
        "help": "Extract measurement instruments from CDE text fields",
        "description": "Detects instrument patterns from 'as part of <Instrument>' phrases",
    },
    "phrase_grouper": {
        "module": "actions.phrase_grouper.cli",
        "help": "Bottom-up k-mer analysis for phrase family discovery",
        "description": "Groups phrases by shared prefix, suffix, or infix patterns",
    },
    "llm_classify": {
        "module": "actions.llm_classify.cli",
        "help": "Classify phrases using multi-LLM queries",
        "description": "Agentic LLM-based classification for phrase curation",
    },
    "diagnose_strip": {
        "module": "actions.diagnose_strip.cli",
        "help": "Diagnose remaining anchor patterns after stripping",
        "description": "Analyze cleaned JSON for iterative stripping improvement",
    },
    "workflow": {
        "module": "actions.workflow.cli",
        "help": "YAML-based workflow orchestrator for CDE analysis pipelines",
        "description": "Execute sequential workflows with checkpoints and resume capability",
    },
    "batch_expand_abbreviations": {
        "module": "actions.batch_expand_abbreviations.cli",
        "help": "Batch expand abbreviations to discover full instrument phrases",
        "description": "Iterate over abbreviations, subset CDEs, and mine phrases to discover extended names",
    },
    "recall_analyze": {
        "module": "actions.recall_analyze.cli",
        "help": "Analyze recall and detect false negatives by instrument family",
        "description": "Compare source data matches against pipeline output to identify gaps",
    },
    "pipeline_report": {
        "module": "actions.pipeline_report.cli",
        "help": "Generate markdown summary reports for pipeline execution",
        "description": "Create human-readable reports with phase summaries and key metrics",
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

        # Run the action and return its exit code
        result = args.func(args)
        return result if result is not None else 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Graceful exit on Ctrl-C without stack trace
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)  # Standard exit code for SIGINT
