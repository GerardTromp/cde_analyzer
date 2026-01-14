"""
Utils - Utility functions and helper modules.

This package contains lightweight utility functions used across the application.

Legacy Kmer Code:
    - kmer_extend_phrases1.py: ACTIVE - Used by logic/phrase_builder.py
    - kmer_legacy_algorithms.py: Consolidated archive of all experimental kmer algorithms
    - legacy_kmer/: Archive directory containing 11 original experimental files

    See utils/legacy_kmer/README.md for detailed algorithm history and evolution.
"""

from .logger import log_if_verbose, logging
from .analyzer_state import get_verbosity, set_verbosity
from .helpers import safe_nested_increment, safe_nested_append
from .constants import MODEL_REGISTRY
from .cli_args import (
    add_input_output_args,
    add_verbosity_args,
    add_model_arg,
    add_field_args,
    add_match_args,
    add_pretty_print_args,
    add_dry_run_arg,
)

__all__ = [
    "log_if_verbose",
    "logging",
    "get_verbosity",
    "set_verbosity",
    "safe_nested_increment",
    "safe_nested_append",
    "MODEL_REGISTRY",
    "add_input_output_args",
    "add_verbosity_args",
    "add_model_arg",
    "add_field_args",
    "add_match_args",
    "add_pretty_print_args",
    "add_dry_run_arg",
]
