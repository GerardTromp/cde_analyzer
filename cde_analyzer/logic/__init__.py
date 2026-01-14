"""
Logic - Business logic implementations for each action.

This package contains the algorithmic implementations separate from CLI and orchestration.
"""

# Import main logic functions to make them accessible
from .counter import count_fields
from .phrase_extractor import extract_phrases
from .html_stripper import strip_html_from_model
from .extract_embed import extract_path

__all__ = [
    "count_fields",
    "extract_phrases",
    "strip_html_from_model",
    "extract_path",
]
