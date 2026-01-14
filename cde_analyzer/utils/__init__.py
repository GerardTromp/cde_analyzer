"""
Utils - Utility functions and helper modules.

This package contains lightweight utility functions used across the application.

Note: Files with 'kmer_*' prefix are legacy experimental code for phrase detection
and are maintained for historical reference only.
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
