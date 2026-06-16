"""DEPRECATED shim — relocated to ``cde_lib.schema.classes`` (ADR-E004).

Re-exports preserved for existing ``from CDE_Schema.classes import ...`` and
``from CDE_Schema import classes`` call sites. Removed at cde_analyzer 2.0.0.
"""

from cde_lib.schema.classes import *  # noqa: F401,F403
