#
# File: actions/strip_branching/cli.py
#
"""
Strip Branching - N-way branching strip producing all variants in a single pass.

Instead of the 10-step branching_strip.yaml pipeline that loads the CDE JSON
multiple times, this engine loads JSON once and computes all 5 variants per CDE
simultaneously.

Note: MT+ST combinations (MTSTPF, MTSTPT) were removed in v0.9.7 because
full instrument removal (inst_full) subsumes sub-instrument removal (inst_sub),
making these variants functionally equivalent to MTSFPF and MTSFPT respectively.

Example:
  cde-analyzer strip_branching -i cdes.json -d output/ \\
      --inst-full-patterns inst_full.tsv \\
      --inst-sub-patterns inst_sub.tsv \\
      --temporal-patterns temporal_expanded.tsv \\
      --phrase-patterns curated_phrases.tsv
"""
import argparse
from argparse import ArgumentParser
from utils.constants import MODEL_REGISTRY

help_text = "N-way branching strip producing all variants in a single pass"
description_text = __doc__


def _get_run_action():
    """Lazy import of run_action to avoid loading heavy dependencies at CLI registration."""
    from .run import run_action
    return run_action


def register_subparser(subparser: ArgumentParser):
    # Required: input and output directory
    subparser.add_argument(
        "--input", "-i", required=True,
        help="Path to input CDE JSON file.",
    )
    subparser.add_argument(
        "--output-dir", "-d", required=True,
        help="Output directory (writes stripped_{CODE}.json per variant).",
    )
    subparser.add_argument(
        "--model", "-m",
        choices=MODEL_REGISTRY.keys(),
        default="CDE",
        help="Top-level Pydantic model name for parsing input JSON.",
    )

    # Pattern files (at least one required for meaningful output)
    subparser.add_argument(
        "--inst-full-patterns",
        help="Full instrument patterns TSV (from --generate-strip-patterns _full.tsv).",
    )
    subparser.add_argument(
        "--inst-sub-patterns",
        help="Sub-group instrument patterns TSV (_sub.tsv).",
    )
    subparser.add_argument(
        "--temporal-patterns",
        help="Expanded temporal patterns TSV (from --expand-temporal-seeds).",
    )
    subparser.add_argument(
        "--phrase-patterns",
        help="Curated phrase patterns TSV.",
    )

    # Variant selection
    subparser.add_argument(
        "--variants",
        type=str,
        default="MTSFPF,MFSTPF,MFSFPT,MTSFPT,MFSTPT",
        help="Comma-separated variant codes to produce (default: all 5). "
             "Valid: MTSFPF, MFSTPF, MFSFPT, MTSFPT, MFSTPT",
    )

    # Processing options
    subparser.add_argument(
        "--workers", "-w",
        type=int,
        default=0,
        help="Parallel workers (0=auto, 1=sequential).",
    )
    subparser.add_argument(
        "--clean-remnants",
        action="store_true",
        help="Post-strip cleanup of orphan articles, floating punctuation, etc.",
    )
    subparser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=["definitions.*.definition", "designations.*.designation"],
        help="Field paths to strip from.",
    )
    subparser.add_argument(
        "--sort-order",
        choices=["length", "file", "alpha"],
        default="length",
        help="Pattern processing order.",
    )
    subparser.add_argument(
        "--verbatim-patterns",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Merge verbatim strip patterns from config into instrument stages "
             "(default: enabled). Use --no-verbatim-patterns to disable.",
    )

    def _lazy_run_action(args):
        """Wrapper for lazy import of run_action."""
        return _get_run_action()(args)

    subparser.set_defaults(func=_lazy_run_action)
