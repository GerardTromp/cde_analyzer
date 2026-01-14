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

__all__ = [
    "log_if_verbose",
    "logging",
    "get_verbosity",
    "set_verbosity",
    "safe_nested_increment",
    "safe_nested_append",
    "MODEL_REGISTRY",
]
