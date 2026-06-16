"""DEPRECATED shim — relocated to ``cde_lib.schema.EmbedText`` (ADR-E004).

Re-exports preserved for existing ``from CDE_Schema.EmbedText import ...`` call
sites. Removed at cde_analyzer 2.0.0.
"""

from cde_lib.schema.EmbedText import *  # noqa: F401,F403
