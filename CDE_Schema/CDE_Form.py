"""DEPRECATED shim — relocated to ``cde_lib.schema.CDE_Form`` (ADR-E004).

Re-exports preserved for existing ``from CDE_Schema.CDE_Form import ...`` call
sites. Removed at cde_analyzer 2.0.0.
"""

from cde_lib.schema.CDE_Form import *  # noqa: F401,F403
