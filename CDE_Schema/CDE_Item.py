"""DEPRECATED shim — relocated to ``cde_lib.schema.CDE_Item`` (ADR-E004).

Re-exports preserved for existing ``from CDE_Schema.CDE_Item import ...`` call
sites. Removed at cde_analyzer 2.0.0.
"""

from cde_lib.schema.CDE_Item import *  # noqa: F401,F403
